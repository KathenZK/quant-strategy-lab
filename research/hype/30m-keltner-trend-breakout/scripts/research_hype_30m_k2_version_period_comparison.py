from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_30m_k2_fq_v2_atrvt_off_backtest as base  # noqa: E402
import research_hype_30m_k2_strict_validation_gates as strict  # noqa: E402
import research_hype_30m_k2_v2_1_dynamic_atr_bracket as dynamic  # noqa: E402
import research_hype_30m_k2_v2_1_loss_regime_filters as regime  # noqa: E402


RUN_DATE = "2026-07-17"
ARTIFACT_DIR = base.ARTIFACT_DIR
SUMMARY_PATH = ARTIFACT_DIR / f"hype_30m_k2_version_period_comparison_{RUN_DATE}.json"
PERIOD_PATH = ARTIFACT_DIR / f"hype_30m_k2_version_period_comparison_{RUN_DATE}.csv"
FULL_PATH = ARTIFACT_DIR / f"hype_30m_k2_version_full_comparison_{RUN_DATE}.csv"
FROZEN_UNTIL = "2026-07-13T06:07:00Z"
WINDOWS = {
    "1w": pd.Timedelta(days=7),
    "1m": pd.Timedelta(days=30),
    "3m": pd.Timedelta(days=90),
    "6m": pd.Timedelta(days=180),
    "1y": pd.Timedelta(days=365),
}


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    args = type(
        "Args",
        (),
        {
            "since": "2025-05-30T00:00:00Z",
            "until": FROZEN_UNTIL,
            "refresh_cache": False,
            "timeout": 45.0,
        },
    )()
    funding_args = type(
        "FundingArgs",
        (),
        {"refresh_data": False, "timeout": 45.0},
    )()
    m1 = base.load_or_fetch_1m(args)
    quality = base.data_quality(m1)
    blockers = sum(
        quality[key]
        for key in (
            "missing_1m_bars",
            "duplicate_ts_rows",
            "invalid_ohlc_rows",
            "critical_null_rows",
        )
    )
    if blockers:
        raise RuntimeError(f"data quality blocker: {quality}")
    return m1, strict.load_or_fetch_funding(funding_args, m1)


def period_rows(
    version: str,
    result: strict.StrictResult,
) -> list[dict[str, Any]]:
    rows = []
    end = result.equity.index.max()
    exits = (
        pd.to_datetime(result.trades["exit_ts"], utc=True)
        if not result.trades.empty
        else pd.Series(dtype="datetime64[ns, UTC]")
    )
    for label, delta in WINDOWS.items():
        requested_start = end - delta
        equity = result.equity.loc[result.equity.index >= requested_start]
        if len(equity) < 2:
            continue
        start = equity.index.min()
        drawdown = equity / equity.cummax() - 1.0
        trades = result.trades.loc[(exits >= start) & (exits <= end)]
        trade_returns = pd.to_numeric(
            trades.get("net_account_return_pct"),
            errors="coerce",
        )
        rows.append(
            {
                "version": version,
                "window": label,
                "start": str(start),
                "end": str(end),
                "return_pct": float(
                    (equity.iloc[-1] / equity.iloc[0] - 1.0) * 100.0
                ),
                "max_drawdown_pct": float(drawdown.min() * 100.0),
                "closed_trades": int(len(trades)),
                "win_rate_pct": float(trade_returns.gt(0.0).mean() * 100.0)
                if len(trades)
                else None,
            }
        )
    return rows


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    m1, funding = load_inputs()
    b30 = base.aggregate_ohlcv(
        m1,
        freq="30min",
        phase_min=0,
        expected_rows=30,
    )[0]
    h1 = base.aggregate_ohlcv(
        m1,
        freq="60min",
        phase_min=0,
        expected_rows=60,
    )[0]
    execution = strict.ExecutionConfig()

    v2_cfg = base.StrategyConfig()
    v21_cfg = dynamic.v21_config()
    v2_features = base.build_features(b30, h1, v2_cfg)
    v21_features = dynamic.v21_features(b30, h1, v21_cfg)
    v3_filter = regime.FilterSpec(
        "combo",
        "pair",
        (),
        (
            regime.FilterSpec("volatility", "atr_pct", (0.0, 0.0125)),
            regime.FilterSpec("quality", "close_location", (0.65,)),
        ),
    )
    v3_features = regime.apply_filter(
        regime.add_features(v21_features),
        v3_filter,
    )
    start = max(
        strict.ready_start(v2_features),
        strict.ready_start(v21_features),
        strict.ready_start(v3_features),
    )
    end = b30.index.max() + pd.Timedelta(minutes=30)
    versions = {
        "External V2 strict": strict.simulate(
            "external_v2_strict",
            v2_features,
            funding,
            v2_cfg,
            execution,
            start_ts=start,
            end_ts=end,
        ),
        "V2.1": strict.simulate(
            "v2_1",
            v21_features,
            funding,
            v21_cfg,
            execution,
            start_ts=start,
            end_ts=end,
        ),
        "V3": strict.simulate(
            "v3",
            v3_features,
            funding,
            v21_cfg,
            execution,
            start_ts=start,
            end_ts=end,
        ),
    }
    if versions["V3"].metrics["trades"] != 78:
        raise RuntimeError(f"V3 parity failed: {versions['V3'].metrics}")

    full = pd.DataFrame(
        [{"version": version, **result.metrics} for version, result in versions.items()]
    )
    periods = pd.DataFrame(
        [
            row
            for version, result in versions.items()
            for row in period_rows(version, result)
        ]
    )
    summary = {
        "family": "HYPE-30M-Keltner-Trend-Breakout",
        "run_date": RUN_DATE,
        "version_note": "No V1 exists in this family; compared actual External V2 strict, V2.1, and V3 identities.",
        "data": {
            "start": str(pd.to_datetime(m1["ts"], utc=True).min()),
            "end": str(pd.to_datetime(m1["ts"], utc=True).max()),
            "rows": int(len(m1)),
            "common_backtest_start": str(start),
            "common_backtest_end": str(end),
        },
        "cost": {
            "fee_per_fill": execution.fee_rate,
            "adverse_slippage_per_fill": execution.slippage_rate,
            "funding_included": execution.include_funding,
        },
        "win_rate_definition": "Trades whose exit timestamp falls inside the slice.",
        "full": full.to_dict(orient="records"),
        "periods": periods.to_dict(orient="records"),
    }
    full.to_csv(FULL_PATH, index=False)
    periods.to_csv(PERIOD_PATH, index=False)
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print("\nFULL")
    print(
        full[
            [
                "version",
                "return_pct",
                "max_drawdown_pct",
                "win_rate_pct",
                "trades",
            ]
        ].to_string(index=False)
    )
    print("\nPERIODS")
    print(
        periods[
            [
                "version",
                "window",
                "return_pct",
                "max_drawdown_pct",
                "win_rate_pct",
                "closed_trades",
            ]
        ].to_string(index=False)
    )
    print("\nsummary", SUMMARY_PATH)


if __name__ == "__main__":
    main()
