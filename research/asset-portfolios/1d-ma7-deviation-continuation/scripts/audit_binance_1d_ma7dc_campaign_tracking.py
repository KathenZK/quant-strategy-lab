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
RUN_DATE = "2026-08-04"
ASSETS = ("HYPE", "BTC", "ETH")
REVERSAL_ATR_VALUES = (1.5, 2.0, 3.0)
EXIT_MODES = ("cross1", "cross2")
PRIMARY_REVERSAL_ATR = 2.0
PRIMARY_DURATION_MIN = 3
PRIMARY_DURATION_MAX = 14
MAX_EXIT_WAIT_DAYS = 30
FEE_RATE = 0.001
SLIPPAGE = 0.0004
EPSILON = 1e-12


def load_base_module() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_ma7dc_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base module: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def detect_completed_swings(
    frame: pd.DataFrame,
    reversal_atr: float,
) -> pd.DataFrame:
    close = frame["close"].to_numpy(float)
    atr = frame["atr7"].to_numpy(float)
    valid = np.flatnonzero(np.isfinite(close) & np.isfinite(atr) & (atr > EPSILON))
    if len(valid) < 3:
        return pd.DataFrame()
    start = int(valid[0])
    direction = 0
    high_index = start
    low_index = start
    pivot_index = start
    extreme_index = start
    rows: list[dict[str, Any]] = []

    def record(side: int, begin: int, end: int, confirmation: int) -> None:
        if end <= begin:
            return
        amplitude = side * math.log(close[end] / close[begin])
        if amplitude <= 0.0:
            return
        duration = end - begin
        rows.append(
            {
                "reversal_atr": reversal_atr,
                "side": side,
                "direction": "long" if side > 0 else "short",
                "start_index": begin,
                "end_index": end,
                "confirmation_index": confirmation,
                "start_visible_ts": frame.index[begin],
                "end_visible_ts": frame.index[end],
                "confirmation_visible_ts": frame.index[confirmation],
                "duration_days": duration,
                "swing_log_amplitude": amplitude,
                "swing_simple_return": side * (close[end] / close[begin] - 1.0),
                "swing_atr_start": abs(close[end] - close[begin]) / atr[begin],
            }
        )

    for index in valid[1:]:
        index = int(index)
        if direction == 0:
            if close[index] >= close[high_index]:
                high_index = index
            if close[index] <= close[low_index]:
                low_index = index
            up_move = close[index] - close[low_index]
            down_move = close[high_index] - close[index]
            if up_move >= reversal_atr * atr[low_index]:
                direction = 1
                pivot_index = low_index
                extreme_index = index
            elif down_move >= reversal_atr * atr[high_index]:
                direction = -1
                pivot_index = high_index
                extreme_index = index
            continue

        if direction > 0:
            if close[index] >= close[extreme_index]:
                extreme_index = index
            reversal = close[extreme_index] - close[index]
            if reversal >= reversal_atr * atr[extreme_index]:
                record(1, pivot_index, extreme_index, index)
                pivot_index = extreme_index
                extreme_index = index
                direction = -1
        else:
            if close[index] <= close[extreme_index]:
                extreme_index = index
            reversal = close[index] - close[extreme_index]
            if reversal >= reversal_atr * atr[extreme_index]:
                record(-1, pivot_index, extreme_index, index)
                pivot_index = extreme_index
                extreme_index = index
                direction = 1

    result = pd.DataFrame(rows)
    if not result.empty:
        result.insert(0, "swing_id", np.arange(1, len(result) + 1))
    return result


def aggregate_daily_funding(hourly: pd.DataFrame) -> pd.Series:
    source = hourly.copy()
    source.index = source.index - pd.Timedelta(hours=1)
    funding = source["funding_rate"].resample("1D", label="left", closed="left").sum()
    funding.index = funding.index + pd.Timedelta(days=1)
    return funding


def adverse_fill(raw_price: float, order_side: int) -> float:
    return raw_price * (1.0 + order_side * SLIPPAGE)


def _exit_signal(frame: pd.DataFrame, index: int, side: int, mode: str) -> bool:
    current = side * (float(frame.iloc[index]["close"]) - float(frame.iloc[index]["sma7"])) < 0.0
    if mode == "cross1":
        return current
    if index <= 0:
        return False
    previous = side * (
        float(frame.iloc[index - 1]["close"]) - float(frame.iloc[index - 1]["sma7"])
    ) < 0.0
    return current and previous


def track_swing(
    asset: str,
    frame: pd.DataFrame,
    funding_daily: pd.Series,
    swing: pd.Series,
    exit_mode: str,
    entry_search_start: int | None = None,
) -> dict[str, Any]:
    side = int(swing["side"])
    start = int(swing["start_index"])
    end = int(swing["end_index"])
    aligned = (
        frame["direction"].eq(side)
        & (side * (frame["close"] - frame["sma7"])).gt(0.0)
    )
    search_start = start if entry_search_start is None else max(start, entry_search_start)
    swing_alignment = aligned.iloc[start : end + 1]
    entry_alignment = aligned.iloc[search_start : end + 1]
    aligned_positions = np.flatnonzero(entry_alignment.to_numpy(bool)) + search_start
    executable_positions = aligned_positions[aligned_positions < end]
    base = {
        "asset": asset,
        "swing_id": int(swing["swing_id"]),
        "reversal_atr": float(swing["reversal_atr"]),
        "direction": swing["direction"],
        "side": side,
        "start_visible_ts": swing["start_visible_ts"],
        "end_visible_ts": swing["end_visible_ts"],
        "duration_days": int(swing["duration_days"]),
        "swing_log_amplitude": float(swing["swing_log_amplitude"]),
        "swing_atr_start": float(swing["swing_atr_start"]),
        "exit_mode": exit_mode,
        "alignment_share": float(swing_alignment.mean()),
        "admitted": bool(len(executable_positions)),
    }
    if not len(executable_positions):
        return {
            **base,
            "timely_admission": False,
            "entry_delay_days": math.nan,
            "entry_signal_visible_ts": pd.NaT,
            "entry_ts": pd.NaT,
            "exit_signal_visible_ts": pd.NaT,
            "exit_ts": pd.NaT,
            "exit_censored": False,
            "premature_exit": False,
            "exit_delay_after_swing_days": math.nan,
            "gross_log_return": math.nan,
            "net_log_return": math.nan,
            "net_positive": False,
            "full_swing_capture": math.nan,
            "available_swing_capture": math.nan,
            "mfe_log_return": math.nan,
            "mfe_retention": math.nan,
            "giveback_share": math.nan,
            "funding_sum": math.nan,
            "entry_bar_index": math.nan,
            "exit_signal_index": math.nan,
            "exit_bar_index": math.nan,
            "round_trips": 0,
            "reentries": 0,
        }

    entry_signal = int(executable_positions[0])
    entry_bar = entry_signal + 1
    entry_ts = frame.index[entry_signal]
    raw_entry = float(frame.iloc[entry_bar]["open"])
    entry_fill = adverse_fill(raw_entry, side)
    timely_limit = min(3, max(1, int(swing["duration_days"]) // 2))
    entry_delay = entry_signal - start

    search_end = min(len(frame) - 2, end + MAX_EXIT_WAIT_DAYS)
    exit_signal: int | None = None
    for index in range(entry_bar, search_end + 1):
        if _exit_signal(frame, index, side, exit_mode):
            exit_signal = index
            break
    censored = exit_signal is None
    if exit_signal is None:
        exit_signal = search_end
    exit_bar = min(exit_signal + 1, len(frame) - 1)
    exit_ts = frame.index[exit_signal]
    raw_exit = float(frame.iloc[exit_bar]["open"])
    exit_fill = adverse_fill(raw_exit, -side)
    gross_log_return = side * math.log(exit_fill / entry_fill)
    funding_slice = funding_daily.loc[(funding_daily.index > entry_ts) & (funding_daily.index <= exit_ts)]
    funding_sum = float(funding_slice.sum())
    net_log_return = gross_log_return - 2.0 * FEE_RATE - side * funding_sum

    path_end = max(entry_bar, exit_bar - 1)
    path = frame.iloc[entry_bar : path_end + 1]
    if side > 0:
        best_price = float(path["high"].max())
        mfe = max(0.0, math.log(best_price / entry_fill))
    else:
        best_price = float(path["low"].min())
        mfe = max(0.0, math.log(entry_fill / best_price))
    retention = gross_log_return / mfe if mfe > EPSILON else math.nan
    giveback = (mfe - gross_log_return) / mfe if mfe > EPSILON else math.nan
    full_amplitude = float(swing["swing_log_amplitude"])
    available_amplitude = side * math.log(float(frame.iloc[end]["close"]) / entry_fill)
    return {
        **base,
        "timely_admission": bool(entry_delay <= timely_limit),
        "entry_delay_days": entry_delay,
        "entry_signal_visible_ts": frame.index[entry_signal],
        "entry_ts": entry_ts,
        "raw_entry": raw_entry,
        "entry_fill": entry_fill,
        "exit_signal_visible_ts": frame.index[exit_signal],
        "exit_ts": exit_ts,
        "raw_exit": raw_exit,
        "exit_fill": exit_fill,
        "exit_censored": censored,
        "premature_exit": bool(exit_signal < end),
        "exit_delay_after_swing_days": exit_signal - end,
        "gross_log_return": gross_log_return,
        "net_log_return": net_log_return,
        "net_positive": bool(net_log_return > 0.0),
        "full_swing_capture": net_log_return / full_amplitude if full_amplitude > EPSILON else math.nan,
        "available_swing_capture": (
            net_log_return / available_amplitude if available_amplitude > EPSILON else math.nan
        ),
        "mfe_log_return": mfe,
        "mfe_retention": retention,
        "giveback_share": giveback,
        "funding_sum": funding_sum,
        "entry_bar_index": entry_bar,
        "exit_signal_index": exit_signal,
        "exit_bar_index": exit_bar,
        "round_trips": 1,
        "reentries": 0,
    }


def track_swing_with_reentries(
    asset: str,
    frame: pd.DataFrame,
    funding_daily: pd.Series,
    swing: pd.Series,
    exit_mode: str,
) -> dict[str, Any]:
    start = int(swing["start_index"])
    end = int(swing["end_index"])
    cursor = start
    legs: list[dict[str, Any]] = []
    for _ in range(20):
        leg = track_swing(
            asset,
            frame,
            funding_daily,
            swing,
            exit_mode,
            entry_search_start=cursor,
        )
        if not leg["admitted"]:
            break
        legs.append(leg)
        if not leg["premature_exit"]:
            break
        next_cursor = int(leg["exit_bar_index"])
        if next_cursor <= cursor or next_cursor >= end:
            break
        cursor = next_cursor
    if not legs:
        empty = track_swing(
            asset,
            frame,
            funding_daily,
            swing,
            exit_mode,
            entry_search_start=start,
        )
        empty["exit_mode"] = f"{exit_mode}_reentry"
        return empty

    first = legs[0]
    last = legs[-1]
    net_return = float(sum(float(leg["net_log_return"]) for leg in legs))
    gross_return = float(sum(float(leg["gross_log_return"]) for leg in legs))
    total_mfe = float(sum(float(leg["mfe_log_return"]) for leg in legs))
    full_amplitude = float(swing["swing_log_amplitude"])
    first_entry_fill = float(first["entry_fill"])
    side = int(swing["side"])
    available_amplitude = side * math.log(float(frame.iloc[end]["close"]) / first_entry_fill)
    retention = gross_return / total_mfe if total_mfe > EPSILON else math.nan
    giveback = (total_mfe - gross_return) / total_mfe if total_mfe > EPSILON else math.nan
    return {
        **first,
        "exit_mode": f"{exit_mode}_reentry",
        "exit_signal_visible_ts": last["exit_signal_visible_ts"],
        "exit_ts": last["exit_ts"],
        "raw_exit": last["raw_exit"],
        "exit_fill": last["exit_fill"],
        "exit_censored": bool(last["exit_censored"]),
        "premature_exit": bool(any(bool(leg["premature_exit"]) for leg in legs)),
        "exit_delay_after_swing_days": last["exit_delay_after_swing_days"],
        "gross_log_return": gross_return,
        "net_log_return": net_return,
        "net_positive": bool(net_return > 0.0),
        "full_swing_capture": net_return / full_amplitude if full_amplitude > EPSILON else math.nan,
        "available_swing_capture": (
            net_return / available_amplitude if available_amplitude > EPSILON else math.nan
        ),
        "mfe_log_return": total_mfe,
        "mfe_retention": retention,
        "giveback_share": giveback,
        "funding_sum": float(sum(float(leg["funding_sum"]) for leg in legs)),
        "exit_signal_index": last["exit_signal_index"],
        "exit_bar_index": last["exit_bar_index"],
        "round_trips": len(legs),
        "reentries": max(0, len(legs) - 1),
    }


def summarize_tracks(tracks: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    duration_scopes = {
        "3_14d": lambda part: part["duration_days"].between(3, 14),
        "all_ge_3d": lambda part: part["duration_days"].ge(3),
        "15_30d": lambda part: part["duration_days"].between(15, 30),
        "31d_plus": lambda part: part["duration_days"].ge(31),
    }
    for keys, grouped in tracks.groupby(
        ["asset", "reversal_atr", "exit_mode", "direction"], sort=True
    ):
        asset, reversal_atr, exit_mode, direction = keys
        for duration_scope, selector in duration_scopes.items():
            part = grouped.loc[selector(grouped)].copy()
            admitted = part.loc[part["admitted"]].copy()
            rows.append(
                {
                    "asset": asset,
                    "reversal_atr": reversal_atr,
                    "exit_mode": exit_mode,
                    "direction": direction,
                    "duration_scope": duration_scope,
                    "completed_swings": int(len(part)),
                    "admitted_swings": int(len(admitted)),
                    "admission_rate": float(part["admitted"].mean()) if len(part) else math.nan,
                    "timely_admission_rate": float(part["timely_admission"].mean()) if len(part) else math.nan,
                    "median_entry_delay_days": float(admitted["entry_delay_days"].median()) if len(admitted) else math.nan,
                    "median_alignment_share": float(part["alignment_share"].median()) if len(part) else math.nan,
                    "median_full_swing_capture": float(admitted["full_swing_capture"].median()) if len(admitted) else math.nan,
                    "weighted_full_swing_capture": (
                        float(admitted["net_log_return"].sum() / admitted["swing_log_amplitude"].sum())
                        if len(admitted) and admitted["swing_log_amplitude"].sum() > EPSILON
                        else math.nan
                    ),
                    "median_available_swing_capture": float(admitted["available_swing_capture"].median()) if len(admitted) else math.nan,
                    "median_mfe_retention": float(admitted["mfe_retention"].median()) if len(admitted) else math.nan,
                    "median_giveback_share": float(admitted["giveback_share"].median()) if len(admitted) else math.nan,
                    "premature_exit_rate": float(admitted["premature_exit"].mean()) if len(admitted) else math.nan,
                    "net_positive_rate": float(admitted["net_positive"].mean()) if len(admitted) else math.nan,
                    "median_net_log_return": float(admitted["net_log_return"].median()) if len(admitted) else math.nan,
                    "median_exit_delay_after_swing_days": (
                        float(admitted["exit_delay_after_swing_days"].median()) if len(admitted) else math.nan
                    ),
                    "censored_exits": int(admitted["exit_censored"].sum()) if len(admitted) else 0,
                    "median_round_trips": float(admitted["round_trips"].median()) if len(admitted) else math.nan,
                    "total_reentries": int(admitted["reentries"].sum()) if len(admitted) else 0,
                }
            )
    return pd.DataFrame(rows)


def build_primary_gate(metrics: pd.DataFrame) -> dict[str, Any]:
    selected = metrics.loc[
        metrics["asset"].eq("HYPE")
        & metrics["reversal_atr"].eq(PRIMARY_REVERSAL_ATR)
        & metrics["exit_mode"].eq("cross1")
        & metrics["direction"].eq("long")
        & metrics["duration_scope"].eq("3_14d")
    ]
    if selected.empty:
        return {"evidence": "insufficient", "reason": "primary row missing"}
    row = selected.iloc[0]
    gates = {
        "admission_rate": bool(float(row["admission_rate"]) >= 0.70),
        "timely_admission_rate": bool(float(row["timely_admission_rate"]) >= 0.60),
        "median_full_swing_capture": bool(float(row["median_full_swing_capture"]) >= 0.50),
        "median_mfe_retention": bool(float(row["median_mfe_retention"]) >= 0.50),
        "exit_and_net": bool(
            float(row["premature_exit_rate"]) <= 0.30
            and float(row["median_net_log_return"]) > 0.0
        ),
    }
    passed = sum(gates.values())
    enough = int(row["completed_swings"]) >= 12
    if enough and passed >= 4:
        evidence = "visual tracking supported"
    elif enough and passed >= 2:
        evidence = "partial"
    elif enough:
        evidence = "not supported"
    else:
        evidence = "insufficient"
    return {
        "evidence": evidence,
        "sample_gate_passed": enough,
        "passed_gates": passed,
        "gates": gates,
        "primary_metrics": row.to_dict(),
    }


def main() -> None:
    base = load_base_module()
    hourly_assets, source_quality = base.load_hourly_assets()
    swing_outputs: list[pd.DataFrame] = []
    track_rows: list[dict[str, Any]] = []
    daily_quality: dict[str, Any] = {}
    for asset in ASSETS:
        daily, quality = base.build_complete_daily(hourly_assets[asset])
        daily = base.build_states(daily)
        funding_daily = aggregate_daily_funding(hourly_assets[asset]).reindex(daily.index).fillna(0.0)
        daily_quality[asset] = {"source": source_quality[asset], "daily": quality}
        for reversal_atr in REVERSAL_ATR_VALUES:
            swings = detect_completed_swings(daily, reversal_atr)
            if swings.empty:
                continue
            swings.insert(0, "asset", asset)
            swing_outputs.append(swings)
            for _, swing in swings.iterrows():
                for exit_mode in EXIT_MODES:
                    track_rows.append(
                        track_swing(asset, daily, funding_daily, swing, exit_mode)
                    )
                    track_rows.append(
                        track_swing_with_reentries(
                            asset, daily, funding_daily, swing, exit_mode
                        )
                    )

    swings_frame = pd.concat(swing_outputs, ignore_index=True)
    tracks_frame = pd.DataFrame(track_rows)
    metrics_frame = summarize_tracks(tracks_frame)
    primary_gate = build_primary_gate(metrics_frame)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    swings_frame.to_csv(
        ARTIFACT_DIR / f"binance_1d_ma7dc_campaign_swings_{RUN_DATE}.csv", index=False
    )
    tracks_frame.to_csv(
        ARTIFACT_DIR / f"binance_1d_ma7dc_campaign_tracks_{RUN_DATE}.csv", index=False
    )
    metrics_frame.to_csv(
        ARTIFACT_DIR / f"binance_1d_ma7dc_campaign_track_metrics_{RUN_DATE}.csv", index=False
    )
    summary = {
        "run_date": RUN_DATE,
        "family": "Binance-1D-MA7-Deviation-Continuation",
        "status": "explore / not promoted / not live-ready",
        "contract": {
            "primary_asset": "HYPE",
            "control_assets": ("BTC", "ETH"),
            "ma": "SMA7",
            "primary_reversal_atr": PRIMARY_REVERSAL_ATR,
            "sensitivity_reversal_atr": REVERSAL_ATR_VALUES,
            "primary_duration_days": (PRIMARY_DURATION_MIN, PRIMARY_DURATION_MAX),
            "primary_exit_mode": "cross1",
            "max_exit_wait_days": MAX_EXIT_WAIT_DAYS,
            "fee_rate": FEE_RATE,
            "slippage": SLIPPAGE,
            "ex_post_swing_is_not_entry_signal": True,
        },
        "data_quality_accepted": bool(
            all(value["daily"]["accepted"] for value in daily_quality.values())
        ),
        "primary_gate": primary_gate,
    }
    (ARTIFACT_DIR / f"binance_1d_ma7dc_campaign_track_summary_{RUN_DATE}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(metrics_frame.loc[metrics_frame["asset"].eq("HYPE")].to_string(index=False))
    print(json.dumps(primary_gate, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
