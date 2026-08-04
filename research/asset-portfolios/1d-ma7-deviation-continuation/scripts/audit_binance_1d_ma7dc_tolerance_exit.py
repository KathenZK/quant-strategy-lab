from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-deviation-continuation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASE_SCRIPT = FAMILY_DIR / "scripts/research_binance_1d_ma7dc.py"
TRACK_SCRIPT = FAMILY_DIR / "scripts/audit_binance_1d_ma7dc_campaign_tracking.py"
RUN_DATE = "2026-08-04"
ASSETS = ("HYPE", "BTC", "ETH")
REVERSAL_ATR_VALUES = (1.5, 2.0, 3.0)
ARMS = (
    "cross1_risk",
    "band05_confirm2_risk",
    "band05_confirm2_mfe50_risk",
)
PRIMARY_REVERSAL_ATR = 2.0
MAX_EXIT_WAIT_DAYS = 30
FEE_RATE = 0.001
SLIPPAGE = 0.0004
HARD_STOP_R = 1.0
SHALLOW_BAND_ATR = 0.5
HARD_BAND_ATR = 1.0
MFE_TRIGGER_R = 2.0
MFE_GIVEBACK_LIMIT = 0.5
EPSILON = 1e-12


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def adverse_fill(raw_price: float, order_side: int) -> float:
    return raw_price * (1.0 + order_side * SLIPPAGE)


def wrong_side_deviation_atr(frame: pd.DataFrame, index: int, side: int) -> float:
    row = frame.iloc[index]
    atr = float(row["atr7"])
    if not math.isfinite(atr) or atr <= EPSILON:
        return math.nan
    signed_gap = side * (float(row["close"]) - float(row["sma7"]))
    return max(0.0, -signed_gap) / atr


def hard_stop_raw_exit(row: pd.Series, stop_price: float, side: int) -> float | None:
    open_price = float(row["open"])
    if side > 0:
        if float(row["low"]) > stop_price:
            return None
        return min(open_price, stop_price)
    if float(row["high"]) < stop_price:
        return None
    return max(open_price, stop_price)


def daily_exit_reason(
    frame: pd.DataFrame,
    index: int,
    side: int,
    arm: str,
    mfe_r: float,
    close_profit_r: float,
) -> str | None:
    deviation = wrong_side_deviation_atr(frame, index, side)
    if arm == "cross1_risk":
        return "cross1" if deviation > 0.0 else None

    if deviation > HARD_BAND_ATR:
        return "band_gt_1atr"
    previous = wrong_side_deviation_atr(frame, index - 1, side) if index > 0 else math.nan
    if deviation > SHALLOW_BAND_ATR and previous > SHALLOW_BAND_ATR:
        return "band_gt_05atr_twice"
    if arm == "band05_confirm2_mfe50_risk" and mfe_r >= MFE_TRIGGER_R:
        giveback = (mfe_r - close_profit_r) / mfe_r
        if giveback > MFE_GIVEBACK_LIMIT:
            return "mfe50"
    return None


def funding_cost_for_leg(
    funding_daily: pd.Series,
    entry_ts: pd.Timestamp,
    exit_visible_ts: pd.Timestamp,
    side: int,
    stop_exit: bool,
) -> float:
    selected = funding_daily.loc[
        (funding_daily.index > entry_ts) & (funding_daily.index <= exit_visible_ts)
    ].astype(float)
    if selected.empty:
        return 0.0
    signed_cost = side * selected
    if stop_exit:
        signed_cost = signed_cost.copy()
        signed_cost.iloc[-1] = max(0.0, float(signed_cost.iloc[-1]))
    return float(signed_cost.sum())


def empty_track(
    asset: str,
    swing: pd.Series,
    arm: str,
    alignment_share: float,
) -> dict[str, Any]:
    return {
        "asset": asset,
        "swing_id": int(swing["swing_id"]),
        "reversal_atr": float(swing["reversal_atr"]),
        "direction": swing["direction"],
        "side": int(swing["side"]),
        "start_visible_ts": swing["start_visible_ts"],
        "end_visible_ts": swing["end_visible_ts"],
        "duration_days": int(swing["duration_days"]),
        "swing_log_amplitude": float(swing["swing_log_amplitude"]),
        "arm": arm,
        "alignment_share": alignment_share,
        "admitted": False,
        "timely_admission": False,
        "entry_delay_days": math.nan,
        "entry_signal_visible_ts": pd.NaT,
        "entry_ts": pd.NaT,
        "entry_fill": math.nan,
        "entry_atr7": math.nan,
        "stop_price": math.nan,
        "exit_signal_visible_ts": pd.NaT,
        "exit_ts": pd.NaT,
        "exit_fill": math.nan,
        "exit_reason": "missed",
        "exit_censored": False,
        "first_exit_premature": False,
        "final_exit_premature": False,
        "exit_delay_after_swing_days": math.nan,
        "gross_log_return": math.nan,
        "net_log_return": math.nan,
        "net_positive": False,
        "full_swing_capture": math.nan,
        "available_swing_capture": math.nan,
        "mfe_log_return": math.nan,
        "mfe_r": math.nan,
        "mfe_retention": math.nan,
        "giveback_share": math.nan,
        "max_intratrade_drawdown_log": math.nan,
        "mae_r": math.nan,
        "holding_days": math.nan,
        "funding_cost": math.nan,
        "fees": math.nan,
        "entry_bar_index": math.nan,
        "exit_signal_index": math.nan,
        "exit_bar_index": math.nan,
        "round_trips": 0,
        "reentries": 0,
        "hard_stop_count": 0,
    }


def track_leg(
    asset: str,
    frame: pd.DataFrame,
    funding_daily: pd.Series,
    swing: pd.Series,
    arm: str,
    entry_search_start: int | None = None,
) -> dict[str, Any]:
    side = int(swing["side"])
    start = int(swing["start_index"])
    end = int(swing["end_index"])
    aligned = frame["direction"].eq(side) & (
        side * (frame["close"] - frame["sma7"])
    ).gt(0.0)
    search_start = start if entry_search_start is None else max(start, entry_search_start)
    swing_alignment = aligned.iloc[start : end + 1]
    entry_alignment = aligned.iloc[search_start : end + 1]
    aligned_positions = np.flatnonzero(entry_alignment.to_numpy(bool)) + search_start
    executable_positions = aligned_positions[aligned_positions < end]
    if not len(executable_positions):
        return empty_track(asset, swing, arm, float(swing_alignment.mean()))

    entry_signal = int(executable_positions[0])
    entry_bar = entry_signal + 1
    entry_ts = frame.index[entry_signal]
    entry_fill = adverse_fill(float(frame.iloc[entry_bar]["open"]), side)
    entry_atr = float(frame.iloc[entry_signal]["atr7"])
    if not math.isfinite(entry_atr) or entry_atr <= EPSILON:
        return empty_track(asset, swing, arm, float(swing_alignment.mean()))
    stop_price = entry_fill - side * HARD_STOP_R * entry_atr
    timely_limit = min(3, max(1, int(swing["duration_days"]) // 2))
    entry_delay = entry_signal - start
    search_end = min(len(frame) - 2, end + MAX_EXIT_WAIT_DAYS)

    best_price = entry_fill
    worst_price = entry_fill
    running_best_close_log = 0.0
    max_drawdown_log = 0.0
    exit_signal: int | None = None
    exit_bar: int | None = None
    raw_exit: float | None = None
    exit_reason: str | None = None
    stop_exit = False

    for index in range(entry_bar, search_end + 1):
        row = frame.iloc[index]
        stop_raw = hard_stop_raw_exit(row, stop_price, side)
        if stop_raw is not None:
            exit_signal = index
            exit_bar = index
            raw_exit = stop_raw
            exit_reason = "hard_stop"
            stop_exit = True
            worst_price = min(worst_price, stop_raw) if side > 0 else max(worst_price, stop_raw)
            break

        if side > 0:
            best_price = max(best_price, float(row["high"]))
            worst_price = min(worst_price, float(row["low"]))
            close_log = math.log(float(row["close"]) / entry_fill)
        else:
            best_price = min(best_price, float(row["low"]))
            worst_price = max(worst_price, float(row["high"]))
            close_log = math.log(entry_fill / float(row["close"]))
        running_best_close_log = max(running_best_close_log, close_log)
        max_drawdown_log = max(max_drawdown_log, running_best_close_log - close_log)
        mfe_r = side * (best_price - entry_fill) / entry_atr
        close_profit_r = side * (float(row["close"]) - entry_fill) / entry_atr
        reason = daily_exit_reason(frame, index, side, arm, mfe_r, close_profit_r)
        if reason is not None:
            exit_signal = index
            exit_bar = index + 1
            raw_exit = float(frame.iloc[exit_bar]["open"])
            exit_reason = reason
            break

    censored = exit_signal is None
    if censored:
        exit_signal = search_end
        exit_bar = search_end + 1
        raw_exit = float(frame.iloc[exit_bar]["open"])
        exit_reason = "censored"

    assert exit_bar is not None and raw_exit is not None and exit_reason is not None
    exit_fill = adverse_fill(raw_exit, -side)
    exit_visible_ts = frame.index[exit_signal]
    gross_log_return = side * math.log(exit_fill / entry_fill)
    funding_cost = funding_cost_for_leg(
        funding_daily,
        entry_ts,
        exit_visible_ts,
        side,
        stop_exit,
    )
    fees = 2.0 * FEE_RATE
    net_log_return = gross_log_return - fees - funding_cost
    if side > 0:
        mfe_log = max(0.0, math.log(best_price / entry_fill))
        mae_r = max(0.0, (entry_fill - worst_price) / entry_atr)
    else:
        mfe_log = max(0.0, math.log(entry_fill / best_price))
        mae_r = max(0.0, (worst_price - entry_fill) / entry_atr)
    mfe_r = side * (best_price - entry_fill) / entry_atr
    retention = gross_log_return / mfe_log if mfe_log > EPSILON else math.nan
    giveback = (mfe_log - gross_log_return) / mfe_log if mfe_log > EPSILON else math.nan
    full_amplitude = float(swing["swing_log_amplitude"])
    available_amplitude = side * math.log(float(frame.iloc[end]["close"]) / entry_fill)
    premature = bool(exit_signal < end)
    return {
        "asset": asset,
        "swing_id": int(swing["swing_id"]),
        "reversal_atr": float(swing["reversal_atr"]),
        "direction": swing["direction"],
        "side": side,
        "start_visible_ts": swing["start_visible_ts"],
        "end_visible_ts": swing["end_visible_ts"],
        "duration_days": int(swing["duration_days"]),
        "swing_log_amplitude": full_amplitude,
        "arm": arm,
        "alignment_share": float(swing_alignment.mean()),
        "admitted": True,
        "timely_admission": bool(entry_delay <= timely_limit),
        "entry_delay_days": entry_delay,
        "entry_signal_visible_ts": frame.index[entry_signal],
        "entry_ts": entry_ts,
        "entry_fill": entry_fill,
        "entry_atr7": entry_atr,
        "stop_price": stop_price,
        "exit_signal_visible_ts": exit_visible_ts,
        "exit_ts": exit_visible_ts,
        "exit_fill": exit_fill,
        "exit_reason": exit_reason,
        "exit_censored": censored,
        "first_exit_premature": premature,
        "final_exit_premature": premature,
        "exit_delay_after_swing_days": exit_signal - end,
        "gross_log_return": gross_log_return,
        "net_log_return": net_log_return,
        "net_positive": bool(net_log_return > 0.0),
        "full_swing_capture": net_log_return / full_amplitude,
        "available_swing_capture": (
            net_log_return / available_amplitude if available_amplitude > EPSILON else math.nan
        ),
        "mfe_log_return": mfe_log,
        "mfe_r": mfe_r,
        "mfe_retention": retention,
        "giveback_share": giveback,
        "max_intratrade_drawdown_log": max_drawdown_log,
        "mae_r": mae_r,
        "holding_days": max(0, exit_bar - entry_bar),
        "funding_cost": funding_cost,
        "fees": fees,
        "entry_bar_index": entry_bar,
        "exit_signal_index": exit_signal,
        "exit_bar_index": exit_bar,
        "round_trips": 1,
        "reentries": 0,
        "hard_stop_count": int(exit_reason == "hard_stop"),
    }


def track_with_reentries(
    asset: str,
    frame: pd.DataFrame,
    funding_daily: pd.Series,
    swing: pd.Series,
    arm: str,
) -> dict[str, Any]:
    start = int(swing["start_index"])
    end = int(swing["end_index"])
    cursor = start
    legs: list[dict[str, Any]] = []
    for _ in range(20):
        leg = track_leg(
            asset,
            frame,
            funding_daily,
            swing,
            arm,
            entry_search_start=cursor,
        )
        if not leg["admitted"]:
            break
        legs.append(leg)
        if not leg["final_exit_premature"]:
            break
        next_cursor = int(leg["exit_bar_index"])
        if next_cursor <= cursor or next_cursor >= end:
            break
        cursor = next_cursor
    if not legs:
        result = track_leg(asset, frame, funding_daily, swing, arm, start)
        result["arm"] = f"{arm}_reentry"
        return result

    first = legs[0]
    last = legs[-1]
    net_return = float(sum(float(leg["net_log_return"]) for leg in legs))
    gross_return = float(sum(float(leg["gross_log_return"]) for leg in legs))
    total_mfe_log = float(sum(float(leg["mfe_log_return"]) for leg in legs))
    full_amplitude = float(swing["swing_log_amplitude"])
    side = int(swing["side"])
    first_entry_fill = float(first["entry_fill"])
    available_amplitude = side * math.log(float(frame.iloc[end]["close"]) / first_entry_fill)
    retention = gross_return / total_mfe_log if total_mfe_log > EPSILON else math.nan
    giveback = (
        (total_mfe_log - gross_return) / total_mfe_log
        if total_mfe_log > EPSILON
        else math.nan
    )
    sequence = ">".join(str(leg["exit_reason"]) for leg in legs)
    return {
        **first,
        "arm": f"{arm}_reentry",
        "exit_signal_visible_ts": last["exit_signal_visible_ts"],
        "exit_ts": last["exit_ts"],
        "exit_fill": last["exit_fill"],
        "exit_reason": sequence,
        "exit_censored": bool(last["exit_censored"]),
        "first_exit_premature": bool(first["final_exit_premature"]),
        "final_exit_premature": bool(last["final_exit_premature"]),
        "exit_delay_after_swing_days": last["exit_delay_after_swing_days"],
        "gross_log_return": gross_return,
        "net_log_return": net_return,
        "net_positive": bool(net_return > 0.0),
        "full_swing_capture": net_return / full_amplitude,
        "available_swing_capture": (
            net_return / available_amplitude if available_amplitude > EPSILON else math.nan
        ),
        "mfe_log_return": total_mfe_log,
        "mfe_r": float(sum(float(leg["mfe_r"]) for leg in legs)),
        "mfe_retention": retention,
        "giveback_share": giveback,
        "max_intratrade_drawdown_log": float(
            max(float(leg["max_intratrade_drawdown_log"]) for leg in legs)
        ),
        "mae_r": float(max(float(leg["mae_r"]) for leg in legs)),
        "holding_days": int(sum(int(leg["holding_days"]) for leg in legs)),
        "funding_cost": float(sum(float(leg["funding_cost"]) for leg in legs)),
        "fees": float(sum(float(leg["fees"]) for leg in legs)),
        "exit_signal_index": last["exit_signal_index"],
        "exit_bar_index": last["exit_bar_index"],
        "round_trips": len(legs),
        "reentries": max(0, len(legs) - 1),
        "hard_stop_count": int(sum(int(leg["hard_stop_count"]) for leg in legs)),
    }


def summarize_tracks(tracks: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    duration_scopes = {
        "3_14d": lambda part: part["duration_days"].between(3, 14),
        "all_ge_3d": lambda part: part["duration_days"].ge(3),
        "15_30d": lambda part: part["duration_days"].between(15, 30),
        "31d_plus": lambda part: part["duration_days"].ge(31),
    }
    grouping = ["asset", "reversal_atr", "arm", "direction"]
    for keys, grouped in tracks.groupby(grouping, sort=True):
        asset, reversal_atr, arm, direction = keys
        for scope, selector in duration_scopes.items():
            part = grouped.loc[selector(grouped)].copy()
            admitted = part.loc[part["admitted"]].copy()
            rows.append(
                {
                    "asset": asset,
                    "reversal_atr": reversal_atr,
                    "arm": arm,
                    "direction": direction,
                    "duration_scope": scope,
                    "completed_swings": int(len(part)),
                    "admitted_swings": int(len(admitted)),
                    "admission_rate": float(part["admitted"].mean()) if len(part) else math.nan,
                    "timely_admission_rate": (
                        float(part["timely_admission"].mean()) if len(part) else math.nan
                    ),
                    "median_full_swing_capture": (
                        float(admitted["full_swing_capture"].median())
                        if len(admitted)
                        else math.nan
                    ),
                    "median_available_swing_capture": (
                        float(admitted["available_swing_capture"].median())
                        if len(admitted)
                        else math.nan
                    ),
                    "median_mfe_retention": (
                        float(admitted["mfe_retention"].median()) if len(admitted) else math.nan
                    ),
                    "median_giveback_share": (
                        float(admitted["giveback_share"].median()) if len(admitted) else math.nan
                    ),
                    "median_intratrade_drawdown_log": (
                        float(admitted["max_intratrade_drawdown_log"].median())
                        if len(admitted)
                        else math.nan
                    ),
                    "median_mae_r": (
                        float(admitted["mae_r"].median()) if len(admitted) else math.nan
                    ),
                    "median_holding_days": (
                        float(admitted["holding_days"].median()) if len(admitted) else math.nan
                    ),
                    "first_premature_exit_rate": (
                        float(admitted["first_exit_premature"].mean())
                        if len(admitted)
                        else math.nan
                    ),
                    "final_premature_exit_rate": (
                        float(admitted["final_exit_premature"].mean())
                        if len(admitted)
                        else math.nan
                    ),
                    "net_positive_rate": (
                        float(admitted["net_positive"].mean()) if len(admitted) else math.nan
                    ),
                    "median_net_log_return": (
                        float(admitted["net_log_return"].median()) if len(admitted) else math.nan
                    ),
                    "median_exit_delay_after_swing_days": (
                        float(admitted["exit_delay_after_swing_days"].median())
                        if len(admitted)
                        else math.nan
                    ),
                    "median_round_trips": (
                        float(admitted["round_trips"].median()) if len(admitted) else math.nan
                    ),
                    "total_reentries": int(admitted["reentries"].sum()) if len(admitted) else 0,
                    "hard_stop_count": (
                        int(admitted["hard_stop_count"].sum()) if len(admitted) else 0
                    ),
                    "censored_exits": (
                        int(admitted["exit_censored"].sum()) if len(admitted) else 0
                    ),
                }
            )
    return pd.DataFrame(rows)


def recent_slice_metrics(tracks: pd.DataFrame, data_end: pd.Timestamp) -> pd.DataFrame:
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=182),
        "1y": pd.Timedelta(days=365),
    }
    rows: list[dict[str, Any]] = []
    grouping = ["asset", "reversal_atr", "arm", "direction"]
    for keys, grouped in tracks.groupby(grouping, sort=True):
        asset, reversal_atr, arm, direction = keys
        for label, delta in windows.items():
            cutoff = data_end - delta
            part = grouped.loc[
                grouped["admitted"]
                & grouped["entry_signal_visible_ts"].gt(cutoff)
                & grouped["entry_signal_visible_ts"].le(data_end)
            ]
            rows.append(
                {
                    "asset": asset,
                    "reversal_atr": reversal_atr,
                    "arm": arm,
                    "direction": direction,
                    "slice": label,
                    "data_end": data_end,
                    "entry_count": int(len(part)),
                    "net_positive_rate": (
                        float(part["net_positive"].mean()) if len(part) else math.nan
                    ),
                    "median_net_log_return": (
                        float(part["net_log_return"].median()) if len(part) else math.nan
                    ),
                    "median_intratrade_drawdown_log": (
                        float(part["max_intratrade_drawdown_log"].median())
                        if len(part)
                        else math.nan
                    ),
                    "total_reentries": int(part["reentries"].sum()) if len(part) else 0,
                }
            )
    return pd.DataFrame(rows)


def build_primary_gate(metrics: pd.DataFrame) -> dict[str, Any]:
    selector = (
        metrics["asset"].eq("HYPE")
        & metrics["reversal_atr"].eq(PRIMARY_REVERSAL_ATR)
        & metrics["direction"].eq("long")
        & metrics["duration_scope"].eq("3_14d")
    )
    primary = metrics.loc[selector].set_index("arm")
    baseline_name = "cross1_risk"
    baseline_reentry_name = f"{baseline_name}_reentry"
    if baseline_name not in primary.index or baseline_reentry_name not in primary.index:
        return {"evidence": "insufficient", "reason": "primary baseline row missing"}
    baseline = primary.loc[baseline_name]
    enough = int(baseline["completed_swings"]) >= 12
    candidates: dict[str, Any] = {}
    for name in ("band05_confirm2_risk", "band05_confirm2_mfe50_risk"):
        reentry_name = f"{name}_reentry"
        if name not in primary.index or reentry_name not in primary.index:
            candidates[name] = {"evidence": "insufficient", "reason": "candidate row missing"}
            continue
        row = primary.loc[name]
        reentry_row = primary.loc[reentry_name]
        baseline_reentry = primary.loc[baseline_reentry_name]
        base_reentries = int(baseline_reentry["total_reentries"])
        candidate_reentries = int(reentry_row["total_reentries"])
        reentry_reduction = (
            (base_reentries - candidate_reentries) / base_reentries
            if base_reentries > 0
            else math.nan
        )
        gates = {
            "capture_delta_15pp": bool(
                float(row["median_full_swing_capture"])
                - float(baseline["median_full_swing_capture"])
                >= 0.15
            ),
            "retention_delta_15pp": bool(
                float(row["median_mfe_retention"])
                - float(baseline["median_mfe_retention"])
                >= 0.15
            ),
            "drawdown_not_worse_5pp": bool(
                float(row["median_intratrade_drawdown_log"])
                - float(baseline["median_intratrade_drawdown_log"])
                <= 0.05
            ),
            "reentries_reduced_30pct": bool(
                math.isfinite(reentry_reduction) and reentry_reduction >= 0.30
            ),
            "net_better_and_positive": bool(
                float(row["median_net_log_return"])
                > float(baseline["median_net_log_return"])
                and float(row["median_net_log_return"]) > 0.0
            ),
        }
        passed = sum(gates.values())
        if not enough:
            evidence = "insufficient"
        elif passed >= 4:
            evidence = "tolerance exit supported"
        elif passed >= 2:
            evidence = "partial"
        else:
            evidence = "not supported"
        candidates[name] = {
            "evidence": evidence,
            "sample_gate_passed": enough,
            "passed_gates": passed,
            "gates": gates,
            "capture_delta_pp": 100.0
            * (
                float(row["median_full_swing_capture"])
                - float(baseline["median_full_swing_capture"])
            ),
            "retention_delta_pp": 100.0
            * (
                float(row["median_mfe_retention"])
                - float(baseline["median_mfe_retention"])
            ),
            "drawdown_delta_pp": 100.0
            * (
                float(row["median_intratrade_drawdown_log"])
                - float(baseline["median_intratrade_drawdown_log"])
            ),
            "reentry_reduction": reentry_reduction,
            "baseline_metrics": baseline.to_dict(),
            "candidate_metrics": row.to_dict(),
        }
    return {
        "sample_gate_passed": enough,
        "completed_swings": int(baseline["completed_swings"]),
        "candidates": candidates,
    }


def main() -> None:
    base = load_module("binance_1d_ma7dc_base_tolerance", BASE_SCRIPT)
    tracking = load_module("binance_1d_ma7dc_tracking_tolerance", TRACK_SCRIPT)
    hourly_assets, source_quality = base.load_hourly_assets()
    tracks: list[dict[str, Any]] = []
    daily_quality: dict[str, Any] = {}
    data_ends: list[pd.Timestamp] = []
    for asset in ASSETS:
        daily, quality = base.build_complete_daily(hourly_assets[asset])
        daily = base.build_states(daily)
        funding_daily = tracking.aggregate_daily_funding(hourly_assets[asset]).reindex(
            daily.index
        ).fillna(0.0)
        daily_quality[asset] = {"source": source_quality[asset], "daily": quality}
        data_ends.append(daily.index.max())
        for reversal_atr in REVERSAL_ATR_VALUES:
            swings = tracking.detect_completed_swings(daily, reversal_atr)
            for _, swing in swings.iterrows():
                for arm in ARMS:
                    tracks.append(track_leg(asset, daily, funding_daily, swing, arm))
                    tracks.append(
                        track_with_reentries(asset, daily, funding_daily, swing, arm)
                    )

    tracks_frame = pd.DataFrame(tracks)
    metrics_frame = summarize_tracks(tracks_frame)
    slices_frame = recent_slice_metrics(tracks_frame, min(data_ends))
    primary_gate = build_primary_gate(metrics_frame)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    tracks_frame.to_csv(
        ARTIFACT_DIR / f"binance_1d_ma7dc_tolerance_exit_tracks_{RUN_DATE}.csv",
        index=False,
    )
    metrics_frame.to_csv(
        ARTIFACT_DIR / f"binance_1d_ma7dc_tolerance_exit_metrics_{RUN_DATE}.csv",
        index=False,
    )
    slices_frame.to_csv(
        ARTIFACT_DIR / f"binance_1d_ma7dc_tolerance_exit_recent_slices_{RUN_DATE}.csv",
        index=False,
    )
    summary = {
        "run_date": RUN_DATE,
        "family": "Binance-1D-MA7-Deviation-Continuation",
        "status": "explore / not promoted / not live-ready",
        "contract": {
            "arms": ARMS,
            "r_price": "1.0 * ATR7 at entry",
            "hard_stop_r": HARD_STOP_R,
            "shallow_band_atr": SHALLOW_BAND_ATR,
            "hard_band_atr": HARD_BAND_ATR,
            "mfe_trigger_r": MFE_TRIGGER_R,
            "mfe_giveback_limit": MFE_GIVEBACK_LIMIT,
            "fee_rate": FEE_RATE,
            "slippage": SLIPPAGE,
            "primary": "HYPE / 2 ATR / long / 3-14d",
            "ex_post_swing_is_not_entry_signal": True,
            "stop_day_funding": "full adverse daily funding; favorable stop-day funding ignored",
        },
        "data_quality_accepted": bool(
            all(value["daily"]["accepted"] for value in daily_quality.values())
        ),
        "data_end": min(data_ends),
        "primary_gate": primary_gate,
    }
    summary_path = (
        ARTIFACT_DIR / f"binance_1d_ma7dc_tolerance_exit_summary_{RUN_DATE}.json"
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    primary_rows = metrics_frame.loc[
        metrics_frame["asset"].eq("HYPE")
        & metrics_frame["reversal_atr"].eq(PRIMARY_REVERSAL_ATR)
        & metrics_frame["direction"].eq("long")
        & metrics_frame["duration_scope"].isin(["3_14d", "all_ge_3d", "31d_plus"])
    ]
    print(primary_rows.to_string(index=False))
    print(json.dumps(primary_gate, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
