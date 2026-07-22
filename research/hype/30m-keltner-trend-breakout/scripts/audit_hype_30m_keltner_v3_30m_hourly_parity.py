from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_30m_k2_fq_v2_atrvt_off_backtest as base  # noqa: E402
import research_hype_30m_k2_strict_validation_gates as strict  # noqa: E402
import research_hype_30m_k2_v2_1_dynamic_atr_bracket as dynamic  # noqa: E402
import research_hype_30m_k2_v2_1_loss_regime_filters as regime  # noqa: E402


RUN_DATE = "2026-07-21"
START = pd.Timestamp("2025-05-30T00:00:00Z")
END = pd.Timestamp("2026-07-13T06:07:00Z")
OUTPUT_PATH = (
    base.ARTIFACT_DIR / f"hype_30m_k2_v3_30m_hourly_parity_{RUN_DATE}.json"
)


def hourly_from_30m(bars: pd.DataFrame) -> pd.DataFrame:
    grouped = bars.resample(
        "60min",
        origin="epoch",
        label="left",
        closed="left",
    )
    hourly = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        quote_volume=("quote_volume", "sum"),
        trade_count=("trade_count", "sum"),
        bar_count=("open", "count"),
    )
    return hourly.loc[hourly["bar_count"].eq(2)].dropna(
        subset=["open", "high", "low", "close"]
    )


def v3_features(
    b30: pd.DataFrame,
    h1: pd.DataFrame,
    config: base.StrategyConfig,
) -> pd.DataFrame:
    filters = regime.FilterSpec(
        "combo",
        "pair",
        (),
        (
            regime.FilterSpec("volatility", "atr_pct", (0.0, 0.0125)),
            regime.FilterSpec("quality", "close_location", (0.65,)),
        ),
    )
    return regime.apply_filter(
        regime.add_features(dynamic.v21_features(b30, h1, config)),
        filters,
    )


def trade_signature(result: strict.StrictResult) -> list[tuple[str, str, str, str]]:
    return [
        (
            str(row.entry_ts),
            str(row.exit_ts),
            str(row.direction),
            str(row.exit_reason),
        )
        for row in result.trades.itertuples()
    ]


def main() -> None:
    m1 = pd.read_parquet(base.CACHE_PATH)
    m1["ts"] = pd.to_datetime(m1["ts"], utc=True)
    m1 = m1.loc[(m1["ts"] >= START) & (m1["ts"] < END)].reset_index(drop=True)
    funding = pd.read_parquet(strict.FUNDING_CACHE)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = funding.loc[
        (funding["ts"] >= START) & (funding["ts"] < END)
    ].reset_index(drop=True)

    b30 = base.aggregate_ohlcv(
        m1,
        freq="30min",
        phase_min=0,
        expected_rows=30,
    )[0]
    direct_h1 = base.aggregate_ohlcv(
        m1,
        freq="60min",
        phase_min=0,
        expected_rows=60,
    )[0]
    rolled_h1 = hourly_from_30m(b30)
    common = direct_h1.index.intersection(rolled_h1.index)
    mismatch_cells: dict[str, int] = {}
    max_abs_difference: dict[str, float] = {}
    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
    ):
        left = direct_h1.loc[common, column].to_numpy("float64")
        right = rolled_h1.loc[common, column].to_numpy("float64")
        mismatch_cells[column] = int(
            (~np.isclose(left, right, rtol=0.0, atol=1e-12, equal_nan=True)).sum()
        )
        max_abs_difference[column] = float(np.nanmax(np.abs(left - right)))

    config = dynamic.v21_config()
    direct_features = v3_features(b30, direct_h1, config)
    rolled_features = v3_features(b30, rolled_h1, config)
    start = max(
        strict.ready_start(direct_features),
        strict.ready_start(rolled_features),
    )
    end = b30.index.max() + pd.Timedelta(minutes=30)
    execution = strict.ExecutionConfig()
    direct = strict.simulate(
        "direct_1m_to_1h",
        direct_features,
        funding,
        config,
        execution,
        start_ts=start,
        end_ts=end,
    )
    rolled = strict.simulate(
        "1m_to_30m_to_1h",
        rolled_features,
        funding,
        config,
        execution,
        start_ts=start,
        end_ts=end,
    )
    result = {
        "strategy": "HYPE-30M-Keltner-Trend-Breakout-V3",
        "data": {
            "start": str(m1["ts"].min()),
            "end": str(m1["ts"].max()),
            "m1_rows": int(len(m1)),
            "bars_30m": int(len(b30)),
            "direct_1h_bars": int(len(direct_h1)),
            "rolled_1h_bars": int(len(rolled_h1)),
            "common_1h_bars": int(len(common)),
        },
        "field_parity": {
            "mismatch_cells_at_1e_12": mismatch_cells,
            "max_abs_difference": max_abs_difference,
        },
        "direct_1h_metrics": direct.metrics,
        "rolled_1h_metrics": rolled.metrics,
        "trade_paths_equal": trade_signature(direct) == trade_signature(rolled),
        "return_delta_pct": rolled.metrics["return_pct"]
        - direct.metrics["return_pct"],
    }
    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
