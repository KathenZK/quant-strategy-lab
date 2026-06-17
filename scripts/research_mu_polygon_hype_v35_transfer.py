from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_ema_cross_strategy import build_features
from research_mu_v35_session_aware import (
    HARD_STOP_ATR,
    TAKE_PROFIT_ATR,
    WARMUP_BARS,
    WINDOWS,
    ResearchSpec,
    add_session_features,
    add_signal_columns,
    buy_hold_metrics,
    compact_original_result,
    compact_result,
    ledger_row,
    make_version_catalog,
    pct,
    run_hype_v35_original,
    run_research_spec,
    window_start_index,
)


POLYGON_PATH = Path(
    "data/external/us_equities/polygon/symbol=mu/timeframe=15m/"
    "mu_15m_2025-06-17_2026-06-17_adjusted.parquet"
)
SUMMARY_PATH = Path("reports/mu_polygon_hype_v35_transfer_summary.json")
TRADES_PATH = Path("reports/mu_polygon_hype_v35_transfer_trades.csv")
EQUITY_PATH = Path("reports/mu_polygon_hype_v35_transfer_equity.csv")
LEDGER_JSON_PATH = Path("reports/mu_polygon_hype_v35_transfer_ledger.json")
LEDGER_CSV_PATH = Path("reports/mu_polygon_hype_v35_transfer_ledger.csv")
ORIGINAL_PATH = Path("reports/mu_polygon_hype_v35_original_summary.json")
ORIGINAL_TRADES_PATH = Path("reports/mu_polygon_hype_v35_original_trades.csv")


def load_polygon() -> pd.DataFrame:
    if not POLYGON_PATH.exists():
        raise FileNotFoundError(f"missing Polygon MU 15m parquet: {POLYGON_PATH}")
    frame = pd.read_parquet(POLYGON_PATH)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.floor("15min")
    frame = frame.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].astype("float64")
    return frame[["ts", "open", "high", "low", "close", "volume"]]


def base_specs() -> list[ResearchSpec]:
    return [
        ResearchSpec(
            name="regular_overnight_v6_long",
            signal_column="v6_regular_overnight_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="regular_overnight_entry_gate",
        ),
        ResearchSpec(
            name="session_gated_v6_long",
            signal_column="v6_regular_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="regular_entry_gate",
        ),
        ResearchSpec(
            name="premarket_regular_v6_long",
            signal_column="v6_premarket_regular_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="premarket_regular_entry_gate",
        ),
        ResearchSpec(
            name="extended_day_v6_long",
            signal_column="v6_extended_day_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="extended_day_entry_gate",
        ),
        ResearchSpec(
            name="premarket_regular_overnight_v6_long",
            signal_column="v6_premarket_regular_overnight_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="premarket_regular_overnight_entry_gate",
        ),
        ResearchSpec(
            name="tradifi_24h5_v6_long",
            signal_column="v6_tradifi_24h5_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="tradifi_24h5_entry_gate",
        ),
        ResearchSpec(
            name="time_v6_long",
            signal_column="v6_long_signal",
            atr_column="atr_pct672",
            trend_column="v6_long_trend_state",
            entry_gate_column="always_entry_gate",
        ),
    ]


def session_counts(frame: pd.DataFrame, start_i: int) -> dict[str, int]:
    suffix = frame.iloc[start_i:]
    return {
        "regular_session_bars_after_warmup": int(suffix.regular_session.sum()),
        "premarket_regular_session_bars_after_warmup": int(
            suffix.premarket_regular_session.sum()
        ),
        "extended_day_session_bars_after_warmup": int(
            suffix.extended_day_session.sum()
        ),
        "regular_overnight_session_bars_after_warmup": int(
            suffix.regular_overnight_session.sum()
        ),
        "premarket_regular_overnight_session_bars_after_warmup": int(
            suffix.premarket_regular_overnight_session.sum()
        ),
        "tradifi_24h5_session_bars_after_warmup": int(suffix.tradifi_24h5_session.sum()),
        "overnight_session_bars_after_warmup": int(suffix.tradifi_overnight_session.sum()),
    }


def all_time_session_counts(frame: pd.DataFrame) -> dict[str, int]:
    return {
        "regular": int(frame.regular_session.sum()),
        "premarket_regular": int(frame.premarket_regular_session.sum()),
        "extended_day": int(frame.extended_day_session.sum()),
        "regular_overnight": int(frame.regular_overnight_session.sum()),
        "premarket_regular_overnight": int(
            frame.premarket_regular_overnight_session.sum()
        ),
        "tradifi_24h5": int(frame.tradifi_24h5_session.sum()),
        "overnight": int(frame.tradifi_overnight_session.sum()),
    }


def main() -> None:
    raw = load_polygon()
    frame = add_signal_columns(add_session_features(build_features(raw)))
    start_i = min(WARMUP_BARS, len(frame) - 1)
    zero_funding = np.zeros(len(frame), dtype="float64")

    original_results = [
        run_hype_v35_original(
            frame,
            funding_rates=zero_funding,
            start_i=start_i,
            entry_gate=None,
            name="B0_polygon_hype_v35_transfer",
        ),
        run_hype_v35_original(
            frame,
            funding_rates=zero_funding,
            start_i=start_i,
            entry_gate=frame.tradifi_24h5_session.to_numpy(dtype=bool),
            name="B0w_polygon_hype_v35_weekend_filtered",
        ),
    ]

    version_catalog = make_version_catalog(base_specs())
    all_results = [
        run_research_spec(frame, item["spec"], start_i=start_i)
        for item in version_catalog
    ]
    equity_frame = pd.concat(
        [result["equity_curve"] for result in all_results],
        axis=1,
    ).reset_index(names="ts")
    trades = pd.DataFrame(
        [
            {**trade, "version": version_catalog[i]["version"]}
            for i, result in enumerate(all_results)
            for trade in result["trades_detail"]
        ]
    )
    compact = [
        {
            "version": version_catalog[i]["version"],
            **compact_result(result),
            "label": version_catalog[i]["label"],
            "entry_session": version_catalog[i]["entry_session"],
        }
        for i, result in enumerate(all_results)
    ]

    ledger_rows: list[dict[str, Any]] = []
    window_results: dict[str, dict[str, Any]] = {}
    for window_label, window_delta in WINDOWS.items():
        current_start_i = window_start_index(
            frame,
            warmup_i=start_i,
            window=window_delta,
        )
        for version_meta in version_catalog:
            result = run_research_spec(
                frame,
                version_meta["spec"],
                start_i=current_start_i,
            )
            row = ledger_row(
                version_meta=version_meta,
                window_label=window_label,
                frame=frame,
                start_i=current_start_i,
                result=result,
            )
            ledger_rows.append(row)
            window_results[f"{version_meta['version']}:{window_label}"] = {
                **row,
                "exit_reasons": result["exit_reasons"],
            }

    benchmark = buy_hold_metrics(frame, start_i)
    original_compact = [compact_original_result(result) for result in original_results]

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(TRADES_PATH, index=False)
    equity_frame.to_csv(EQUITY_PATH, index=False)
    pd.DataFrame(ledger_rows).to_csv(LEDGER_CSV_PATH, index=False)
    pd.DataFrame(
        [
            trade
            for result in original_results
            for trade in result["trades_detail"]
        ]
    ).to_csv(ORIGINAL_TRADES_PATH, index=False)
    ORIGINAL_PATH.write_text(
        json.dumps(
            {
                "symbol": "MU",
                "source": "polygon",
                "source_strategy": "HYPE trend-breakout V35 transferred to MU",
                "data": {
                    "rows": int(len(frame)),
                    "start": str(pd.Timestamp(frame.ts.iloc[0])),
                    "end": str(pd.Timestamp(frame.ts.iloc[-1])),
                    "warmup_bars": int(start_i),
                    "backtest_start_after_warmup": str(
                        pd.Timestamp(frame.ts.iloc[start_i])
                    ),
                    "session_counts": all_time_session_counts(frame),
                },
                "assumptions": {
                    "funding": "zero; Polygon is spot equity aggregate data",
                    "entry_delay": "K0 signal, K2 open entry",
                    "direction": "long and short",
                    "max_allocation": 3.0,
                    "take_profit_atr": 5.0,
                    "hard_stop_atr": 7.0,
                },
                "results": original_compact,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    LEDGER_JSON_PATH.write_text(
        json.dumps(
            {
                "symbol": "MU",
                "source": "polygon",
                "versions": [
                    {key: value for key, value in item.items() if key != "spec"}
                    for item in version_catalog
                ],
                "windows": window_results,
                "rows": ledger_rows,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    SUMMARY_PATH.write_text(
        json.dumps(
            {
                "symbol": "MU",
                "source": "polygon",
                "data": {
                    "path": str(POLYGON_PATH),
                    "rows": int(len(frame)),
                    "start": str(pd.Timestamp(frame.ts.iloc[0])),
                    "end": str(pd.Timestamp(frame.ts.iloc[-1])),
                    "warmup_bars": int(start_i),
                    "backtest_start_after_warmup": str(
                        pd.Timestamp(frame.ts.iloc[start_i])
                    ),
                    **session_counts(frame, start_i),
                },
                "assumptions": {
                    "session_timezone": "America/New_York",
                    "polygon_session_coverage": "04:00-20:00 ET only in the downloaded aggregates; no 20:00-04:00 ET overnight bars",
                    "position_side": "long-only for V-series; B0 keeps original long/short HYPE V35 diagnostic",
                    "tested_allocations": [2.0, 3.0],
                    "take_profit_atr": TAKE_PROFIT_ATR,
                    "hard_stop_atr": HARD_STOP_ATR,
                },
                "buy_hold_after_warmup": {
                    "return_pct": pct(benchmark["return"]),
                    "max_dd_pct": pct(benchmark["max_dd"]),
                },
                "original_hype_v35": {
                    "json": str(ORIGINAL_PATH),
                    "trades": str(ORIGINAL_TRADES_PATH),
                    "results": original_compact,
                },
                "version_catalog": [
                    {
                        key: value
                        for key, value in item.items()
                        if key != "spec"
                    }
                    for item in version_catalog
                ],
                "variants": compact,
                "ledger": {
                    "json": str(LEDGER_JSON_PATH),
                    "csv": str(LEDGER_CSV_PATH),
                },
                "notes": [
                    "V1 regular+overnight degenerates to regular-only on Polygon because no overnight bars were returned.",
                    "V5/V7/V9/V11 become close variants on Polygon because only 04:00-20:00 ET bars exist.",
                    "Sharpe annualization follows the existing HYPE research constant for comparability with prior local reports.",
                ],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "summary": str(SUMMARY_PATH),
                "ledger": str(LEDGER_CSV_PATH),
                "top_all": sorted(
                    [row for row in ledger_rows if row["window"] == "ALL"],
                    key=lambda row: row["return_pct"],
                    reverse=True,
                )[:5],
                "buy_hold_after_warmup": {
                    "return_pct": pct(benchmark["return"]),
                    "max_dd_pct": pct(benchmark["max_dd"]),
                },
                "original_hype_v35": original_compact,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
