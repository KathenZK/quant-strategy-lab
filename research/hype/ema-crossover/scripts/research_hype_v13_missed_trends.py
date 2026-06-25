from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from compare_hype_ema_v2_v4 import entry_signal
from research_hype_ema_cross_strategy import build_features
from research_hype_ema_oscillator_top_exit_v10 import add_oscillator_features
from research_hype_ema_regime_hold_v5 import load_hype_data_lake
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_ema_volume_overlay_v8 import v6_variant
from research_hype_state_machine_v12 import V12Spec, add_structure_features, run_v12
from research_hype_state_machine_v12_hard_exit import spec as focused_spec
from research_hype_v13_main_backfill import v13_spec


REPORT_PATH = Path("research/hype/ema-crossover/artifacts/hype_v13_missed_trends.json")
CANDIDATE_PATH = Path("research/hype/ema-crossover/artifacts/hype_v13_missed_trends_candidates.csv")
REGIME_PATH = Path("research/hype/ema-crossover/artifacts/hype_v13_missed_trends_regimes.csv")
SKIPPED_TRADE_PATH = Path("research/hype/ema-crossover/artifacts/hype_v13_missed_trends_skipped_v12_3_trades.csv")
REJECTED_EPISODE_PATH = Path("research/hype/ema-crossover/artifacts/hype_v13_missed_trends_rejected_signal_episodes.csv")


def make_spec(name: str, *, age: int, dist: float = 0.0, move48: float = 0.0) -> V12Spec:
    return focused_spec(
        name,
        hard_exit_mode="swing96",
        volume_warning_mode="no_mfi_div",
        warning_exit_min_capture=0.35,
        entry_max_regime_age=age,
        entry_max_dist_ema96=dist,
        entry_max_move48=move48,
    )


def pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": result["name"],
        "return": result["return"],
        "max_dd": result["max_dd"],
        "sharpe": result["sharpe"],
        "trades": result["trades"],
        "win_rate": result["win_rate"],
        "avg_trade_pct": result["avg_trade_pct"],
        "median_trade_pct": result["median_trade_pct"],
        "best_trade_pct": result["best_trade_pct"],
        "worst_trade_pct": result["worst_trade_pct"],
        "avg_hold_bars": result["avg_hold_bars"],
        "entry_max_regime_age": result["entry_max_regime_age"],
        "entry_max_dist_ema96": result["entry_max_dist_ema96"],
        "entry_max_move48": result["entry_max_move48"],
        "exit_reasons": result["exit_reasons"],
    }


def add_regime_id(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    sign = np.sign(result.ema_spread.to_numpy("float64"))
    sign[sign == 0] = np.nan
    sign_series = pd.Series(sign).ffill().fillna(0).astype(int).to_numpy()
    cross = np.r_[True, sign_series[1:] != sign_series[:-1]]
    result["regime_id"] = np.cumsum(cross)
    result["regime_direction"] = sign_series
    return result


def assign_trade_regime(frame: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    ts_to_regime = frame.set_index(pd.to_datetime(frame.ts, utc=True))["regime_id"]
    result = trades.copy()
    result["entry_dt"] = pd.to_datetime(result.entry_ts, utc=True)
    result["regime_id"] = result["entry_dt"].map(ts_to_regime).astype("Int64")
    return result


def summarize_regimes(frame: pd.DataFrame, trades_by_name: dict[str, pd.DataFrame], start_ts: pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    working = frame[pd.to_datetime(frame.ts, utc=True) >= start_ts].copy()
    for regime_id, group in working.groupby("regime_id"):
        direction = int(group.regime_direction.iloc[0])
        if direction == 0 or len(group) < 16:
            continue
        start_close = float(group.close.iloc[0])
        if direction > 0:
            potential = float(group.high.max() / start_close - 1)
            close_move = float(group.close.iloc[-1] / start_close - 1)
        else:
            potential = float(1 - group.low.min() / start_close)
            close_move = float(1 - group.close.iloc[-1] / start_close)
        row: dict[str, Any] = {
            "regime_id": int(regime_id),
            "side": "long" if direction > 0 else "short",
            "start_ts": str(pd.Timestamp(group.ts.iloc[0])),
            "end_ts": str(pd.Timestamp(group.ts.iloc[-1])),
            "bars": int(len(group)),
            "potential_move": potential,
            "close_to_close_move": close_move,
            "base_signal_bars": int(np.count_nonzero(group.base_signal.to_numpy())),
        }
        for name, trades in trades_by_name.items():
            subset = trades[trades.regime_id == regime_id]
            row[f"{name}_trades"] = int(len(subset))
            row[f"{name}_pnl_sum"] = float(subset.pnl_pct.sum()) if len(subset) else 0.0
            row[f"{name}_mfe_atr_sum"] = float(subset.mfe_atr.sum()) if len(subset) else 0.0
        rows.append(row)
    return pd.DataFrame(rows).sort_values("potential_move", ascending=False)


def skipped_v12_3_trades(v12_3: pd.DataFrame, v13: pd.DataFrame) -> pd.DataFrame:
    if v12_3.empty:
        return v12_3.copy()
    v13_entries = set(pd.to_datetime(v13.entry_ts, utc=True).astype(str)) if not v13.empty else set()
    result = v12_3.copy()
    result["entry_key"] = pd.to_datetime(result.entry_ts, utc=True).astype(str)
    result = result[~result.entry_key.isin(v13_entries)].copy()
    return result.sort_values("pnl_pct", ascending=False)


def rejection_reason(row: pd.Series, direction: int) -> str:
    reasons = []
    age = float(row.regime_age)
    if np.isfinite(age) and age > 128:
        reasons.append("age_gt_128")
    ema96 = float(row.ema96)
    if not np.isfinite(ema96) or ema96 <= 0:
        reasons.append("ema96_invalid")
    else:
        dist = direction * (float(row.close) / ema96 - 1)
        if dist > 0.08:
            reasons.append("dist_gt_8pct")
    return "+".join(reasons) if reasons else "allowed_by_v13_filter"


def rejected_signal_episodes(frame: pd.DataFrame, v13_trades: pd.DataFrame, start_ts: pd.Timestamp) -> pd.DataFrame:
    signal = frame.base_signal.to_numpy()
    ts = pd.to_datetime(frame.ts, utc=True)
    in_trade = np.zeros(len(frame), dtype=bool)
    for trade in v13_trades.itertuples():
        entry_ts = pd.Timestamp(trade.entry_ts)
        exit_ts = pd.Timestamp(trade.exit_ts)
        entry_matches = np.flatnonzero(ts == entry_ts)
        if len(entry_matches):
            # Entry is placed on the bar after the signal, so the previous signal bar is not a missed opportunity.
            in_trade[max(0, int(entry_matches[0]) - 1)] = True
        in_trade |= (ts >= entry_ts) & (ts <= exit_ts)

    rows = []
    active: dict[str, Any] | None = None
    for i, direction in enumerate(signal):
        if ts.iloc[i] < start_ts or direction == 0 or in_trade[i]:
            if active is not None:
                rows.append(active)
                active = None
            continue
        reason = rejection_reason(frame.iloc[i], int(direction))
        regime_id = int(frame.regime_id.iloc[i])
        key = (regime_id, int(direction), reason)
        if active is None or active["key"] != key or i != active["last_i"] + 1:
            if active is not None:
                rows.append(active)
            active = {
                "key": key,
                "regime_id": regime_id,
                "side": "long" if direction > 0 else "short",
                "reason": reason,
                "start_i": i,
                "last_i": i,
                "signals": 1,
            }
        else:
            active["last_i"] = i
            active["signals"] += 1
    if active is not None:
        rows.append(active)

    out_rows = []
    for row in rows:
        start_i = int(row["start_i"])
        end_i = int(row["last_i"])
        regime_id = int(row["regime_id"])
        direction = 1 if row["side"] == "long" else -1
        future = frame[(frame.index >= start_i) & (frame.regime_id == regime_id)]
        if future.empty:
            continue
        base = float(frame.close.iloc[start_i])
        if direction > 0:
            future_move = float(future.high.max() / base - 1)
        else:
            future_move = float(1 - future.low.min() / base)
        out_rows.append(
            {
                "regime_id": regime_id,
                "side": row["side"],
                "reason": row["reason"],
                "start_ts": str(pd.Timestamp(frame.ts.iloc[start_i])),
                "end_ts": str(pd.Timestamp(frame.ts.iloc[end_i])),
                "signals": int(row["signals"]),
                "age_start": float(frame.regime_age.iloc[start_i]),
                "dist_start": float(direction * (frame.close.iloc[start_i] / frame.ema96.iloc[start_i] - 1)),
                "future_move": future_move,
            }
        )
    return pd.DataFrame(out_rows).sort_values("future_move", ascending=False)


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_regime_id(add_structure_features(add_oscillator_features(add_volume_features(build_features(raw)))))
    frame["base_signal"] = entry_signal(frame, v6_variant())
    start_ts = pd.Timestamp(frame.ts.iloc[-1]) - pd.Timedelta(days=365)

    specs = [
        make_spec("V12_3_no_entry_filter", age=0),
        make_spec("V12_4_age128", age=128),
        v13_spec(),
        make_spec("V13_age192_dist08", age=192, dist=0.08),
        make_spec("V13_age256_dist08", age=256, dist=0.08),
        make_spec("V13_age384_dist08", age=384, dist=0.08),
        make_spec("V13_no_age_dist08", age=0, dist=0.08),
        make_spec("V13_age128_dist10", age=128, dist=0.10),
        make_spec("V13_age128_dist12", age=128, dist=0.12),
        make_spec("V13_age192_dist10", age=192, dist=0.10),
        make_spec("V13_age256_dist10", age=256, dist=0.10),
        make_spec("V13_age128_dist08_move12", age=128, dist=0.08, move48=0.12),
    ]
    raw_results = [run_v12(frame, spec, start_ts=start_ts, collect_trades=True) for spec in specs]
    candidate = pd.DataFrame([compact_result(result) for result in raw_results]).sort_values(
        ["return", "max_dd"], ascending=[False, False]
    )
    trades_by_name = {
        result["name"]: assign_trade_regime(frame, pd.DataFrame(result["trades_detail"]))
        for result in raw_results
    }
    regime_summary = summarize_regimes(
        frame,
        {
            "v12_3": trades_by_name["V12_3_no_entry_filter"],
            "age128": trades_by_name["V12_4_age128"],
            "v13": trades_by_name["V13_age128_dist08"],
        },
        start_ts,
    )
    skipped = skipped_v12_3_trades(trades_by_name["V12_3_no_entry_filter"], trades_by_name["V13_age128_dist08"])
    rejected = rejected_signal_episodes(frame, trades_by_name["V13_age128_dist08"], start_ts)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    candidate.to_csv(CANDIDATE_PATH, index=False)
    regime_summary.to_csv(REGIME_PATH, index=False)
    skipped.to_csv(SKIPPED_TRADE_PATH, index=False)
    rejected.to_csv(REJECTED_EPISODE_PATH, index=False)

    report = {
        "data": {
            "start": str(start_ts),
            "end": str(pd.Timestamp(frame.ts.iloc[-1])),
        },
        "candidates": candidate.to_dict(orient="records"),
        "top_missed_regimes": regime_summary[
            (regime_summary["potential_move"] >= 0.15) & (regime_summary["v13_trades"] == 0)
        ]
        .head(10)
        .to_dict(orient="records"),
        "skipped_v12_3_summary": {
            "skipped_trades": int(len(skipped)),
            "positive_skipped": int((skipped.pnl_pct > 0).sum()) if len(skipped) else 0,
            "negative_skipped": int((skipped.pnl_pct <= 0).sum()) if len(skipped) else 0,
            "skipped_pnl_sum": float(skipped.pnl_pct.sum()) if len(skipped) else 0.0,
            "top_skipped": skipped.head(10).to_dict(orient="records"),
        },
        "rejected_signal_summary": {
            "episodes": int(len(rejected)),
            "future_move_ge_15pct": int((rejected.future_move >= 0.15).sum()) if len(rejected) else 0,
            "by_reason": rejected.groupby("reason").agg(
                episodes=("reason", "size"),
                future_move_ge_15pct=("future_move", lambda item: int((item >= 0.15).sum())),
                max_future_move=("future_move", "max"),
            ).reset_index().to_dict(orient="records")
            if len(rejected)
            else [],
            "top_rejected": rejected.head(12).to_dict(orient="records"),
        },
        "specs": [asdict(spec) for spec in specs],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"wrote={REPORT_PATH}")
    print(f"candidates={CANDIDATE_PATH}")
    print(candidate[["name", "return", "max_dd", "sharpe", "trades", "win_rate", "entry_max_regime_age", "entry_max_dist_ema96"]].to_string(index=False))
    print("\\nskipped_v12_3", report["skipped_v12_3_summary"])
    print("\\nrejected_by_reason")
    print(pd.DataFrame(report["rejected_signal_summary"]["by_reason"]).to_string(index=False))


if __name__ == "__main__":
    main()
