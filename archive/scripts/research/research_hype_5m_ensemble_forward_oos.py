from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_ensemble_combo import IS_END_TS, START_TS, choose_one_position, metric_from_rows
from research_hype_5m_filter_refinement import feature_values, row_to_config
from research_hype_5m_indicator_search import add_features, build_signal, simulate_trades


DATA_ROOT = Path("data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=5m")
SYMBOL_FILE = "symbol=hype_usdt_usdt.parquet"
LEGS_PATH = Path("reports/hype_5m_ensemble_combo_legs.csv")
REPORT_PATH = Path("reports/hype_5m_ensemble_forward_oos.json")
SUMMARY_PATH = Path("reports/hype_5m_ensemble_forward_oos_summary.csv")
TRADES_PATH = Path("reports/hype_5m_ensemble_forward_oos_trades.csv")
LEG_TRADES_PATH = Path("reports/hype_5m_ensemble_forward_oos_leg_trades.csv")

ORIGINAL_END_TS = pd.Timestamp("2026-06-01T00:00:00Z")
FORWARD_START_TS = pd.Timestamp("2026-06-01T00:00:00Z")
TARGET_COMBOS: tuple[tuple[str, int, float], ...] = (
    ("S01", 8, 4.0),
    ("S02", 16, 2.5),
    ("S03", 8, 3.0),
    ("S04", 12, 2.5),
    ("S05", 5, 3.0),
    ("S06", 16, 2.0),
    ("S07", 8, 2.5),
)
UNIQUE_PATHS: tuple[tuple[str, int], ...] = (
    ("P05", 5),
    ("P08", 8),
    ("P12", 12),
    ("P16", 16),
)


def load_hype_5m() -> pd.DataFrame:
    files = sorted(DATA_ROOT.glob(f"date=*/{SYMBOL_FILE}"))
    if not files:
        raise FileNotFoundError(f"no local HYPE 5m parquet files under {DATA_ROOT}")
    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    frame = frame.loc[frame["ts"] >= START_TS].reset_index(drop=True)
    expected = pd.date_range(frame["ts"].iloc[0], frame["ts"].iloc[-1], freq="5min")
    missing = expected.difference(frame["ts"])
    if len(missing):
        raise RuntimeError(f"HYPE 5m data has {len(missing)} missing bars, first={missing[0]}")
    return frame


def parse_filter_part(part: str) -> tuple[str, str, float]:
    feature, op, threshold = part.rsplit("_", 2)
    if op not in {"ge", "le"}:
        raise ValueError(f"unsupported filter operator in {part}")
    return feature, op, float(threshold)


def apply_refinement_filter(frame: pd.DataFrame, leg: pd.Series) -> list[dict[str, Any]]:
    cfg = row_to_config(leg)
    base_signal = build_signal(frame, cfg)
    sig_idx = np.flatnonzero(base_signal)
    if len(sig_idx) == 0:
        return []
    values = feature_values(frame, cfg, base_signal, sig_idx)
    keep = np.ones(len(sig_idx), dtype=bool)
    for part in str(leg["filter_name"]).split("&"):
        feature, op, threshold = parse_filter_part(part)
        if feature not in values:
            raise KeyError(f"{feature} not available for {leg['refined_name']}")
        if op == "ge":
            keep &= values[feature] >= threshold
        else:
            keep &= values[feature] <= threshold
    filtered_signal = np.zeros_like(base_signal)
    filtered_signal[sig_idx[keep]] = base_signal[sig_idx[keep]]
    trades = simulate_trades(frame, filtered_signal, cfg)
    rows: list[dict[str, Any]] = []
    for trade in trades:
        item = asdict(trade)
        item["refined_name"] = str(leg["refined_name"])
        item["base_name"] = str(leg["base_name"])
        item["leg_rank"] = int(leg["leg_rank"])
        item["side_mode"] = str(leg["side_mode"])
        rows.append(item)
    return rows


def max_hold_by_name(legs: pd.DataFrame) -> dict[str, int]:
    return {str(row["refined_name"]): int(row["max_hold_bars"]) for _, row in legs.iterrows()}


def marked_open_count(rows: list[dict[str, Any]], max_hold_map: dict[str, int], latest_ts: pd.Timestamp) -> int:
    count = 0
    for row in rows:
        if row["exit_ts"] != latest_ts or row["reason"] != "time":
            continue
        max_hold = max_hold_map.get(str(row["refined_name"]), 0)
        if int(row["bars_held"]) < max_hold:
            count += 1
    return count


def prefixed(metrics: dict[str, Any], prefix: str) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in metrics.items()}


def metrics_for_period(
    rows: list[dict[str, Any]],
    leverage: float,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    return metric_from_rows(rows, leverage, start=start, end=end)


def main() -> None:
    legs = pd.read_csv(LEGS_PATH)
    legs["leg_rank"] = np.arange(1, len(legs) + 1)
    frame = add_features(load_hype_5m())
    latest_ts = pd.Timestamp(frame["ts"].iloc[-1])
    forward_end = latest_ts + pd.Timedelta(minutes=5)
    forward_frame = frame.loc[frame["ts"] >= FORWARD_START_TS].copy()

    all_leg_rows: list[dict[str, Any]] = []
    for _, leg in legs.iterrows():
        all_leg_rows.extend(apply_refinement_filter(frame, leg))
    leg_trades = pd.DataFrame(all_leg_rows)
    if leg_trades.empty:
        raise RuntimeError("no leg trades generated")

    max_hold_map = max_hold_by_name(legs)
    summary_rows: list[dict[str, Any]] = []
    selected_trade_rows: list[dict[str, Any]] = []

    for strategy_id, count, leverage in TARGET_COMBOS:
        names = legs.head(count)["refined_name"].tolist()
        selected = choose_one_position(leg_trades, names)
        for row in selected:
            copied = dict(row)
            copied["strategy_id"] = strategy_id
            copied["legs"] = count
            copied["leverage"] = leverage
            selected_trade_rows.append(copied)
        oos_original = metrics_for_period(selected, leverage, start=IS_END_TS, end=ORIGINAL_END_TS)
        forward = metrics_for_period(selected, leverage, start=FORWARD_START_TS, end=forward_end)
        full_extended = metrics_for_period(selected, leverage, start=START_TS, end=forward_end)
        forward_rows = [row for row in selected if FORWARD_START_TS <= row["entry_ts"] < forward_end]
        side_counts = pd.Series([int(row["side"]) for row in forward_rows]).value_counts().to_dict()
        summary_rows.append(
            {
                "strategy_id": strategy_id,
                "path_id": f"P{count:02d}",
                "legs": count,
                "leverage": leverage,
                "forward_start": FORWARD_START_TS.isoformat(),
                "forward_end_exclusive": forward_end.isoformat(),
                "latest_bar": latest_ts.isoformat(),
                "forward_marked_open_trades": marked_open_count(forward_rows, max_hold_map, latest_ts),
                "forward_long_trades": int(side_counts.get(1, 0)),
                "forward_short_trades": int(side_counts.get(-1, 0)),
                **prefixed(oos_original, "original_oos"),
                **prefixed(forward, "forward"),
                **prefixed(full_extended, "full_extended"),
            }
        )

    path_rows: list[dict[str, Any]] = []
    for path_id, count in UNIQUE_PATHS:
        names = legs.head(count)["refined_name"].tolist()
        selected = choose_one_position(leg_trades, names)
        forward_rows = [row for row in selected if FORWARD_START_TS <= row["entry_ts"] < forward_end]
        side_counts = pd.Series([int(row["side"]) for row in forward_rows]).value_counts().to_dict()
        path_rows.append(
            {
                "path_id": path_id,
                "legs": count,
                "forward_trades": len(forward_rows),
                "forward_long_trades": int(side_counts.get(1, 0)),
                "forward_short_trades": int(side_counts.get(-1, 0)),
                "forward_marked_open_trades": marked_open_count(forward_rows, max_hold_map, latest_ts),
            }
        )

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(summary_rows)
    selected_trades = pd.DataFrame(selected_trade_rows)
    summary.to_csv(SUMMARY_PATH, index=False)
    selected_trades.to_csv(TRADES_PATH, index=False)
    leg_trades.to_csv(LEG_TRADES_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "data": {
                    "symbol": "HYPE/USDT:USDT",
                    "exchange": "binance",
                    "market_type": "perp",
                    "timeframe": "5m",
                    "first_bar": frame["ts"].iloc[0].isoformat(),
                    "latest_bar": latest_ts.isoformat(),
                    "rows": int(len(frame)),
                    "forward_start": FORWARD_START_TS.isoformat(),
                    "forward_end_exclusive": forward_end.isoformat(),
                    "forward_rows": int(len(forward_frame)),
                    "forward_open": float(forward_frame["open"].iloc[0]),
                    "forward_close": float(forward_frame["close"].iloc[-1]),
                    "forward_return": float(forward_frame["close"].iloc[-1] / forward_frame["open"].iloc[0] - 1.0),
                    "forward_high": float(forward_frame["high"].max()),
                    "forward_low": float(forward_frame["low"].min()),
                },
                "method": {
                    "note": "rebuild refined leg signals on the extended data lake, then apply the same one-position ensemble logic",
                    "marked_open_trades": "trades that reach latest_bar before max_hold are marked to latest close by the inherited simulator",
                },
                "unique_paths": path_rows,
                "summary": summary_rows,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"summary={SUMMARY_PATH}")
    print(f"selected_trades={TRADES_PATH}")
    print(f"leg_trades={LEG_TRADES_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
