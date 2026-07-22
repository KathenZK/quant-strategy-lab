"""读取已审计数据并检查 HYPE 30m Keltner V3 的未来延伸。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
KELTNER_15M_SCRIPT_DIR = (
    SCRIPT_DIR.parents[1] / "15m-keltner-trend-breakout/scripts"
)
if str(KELTNER_15M_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(KELTNER_15M_SCRIPT_DIR))

import research_hype_15m_keltner_only as source15  # noqa: E402  # pyright: ignore[reportMissingImports]
import research_hype_30m_k2_fq_v2_atrvt_off_backtest as base  # noqa: E402
import research_hype_30m_k2_strict_validation_gates as strict  # noqa: E402
import research_hype_30m_k2_v2_1_dynamic_atr_bracket as dynamic  # noqa: E402
import research_hype_30m_k2_v2_1_loss_regime_filters as regime  # noqa: E402


RUN_DATE = "2026-07-21"
FROZEN_UNTIL = pd.Timestamp("2026-07-13T06:07:00Z")
PROSPECTIVE_START = FROZEN_UNTIL.floor("30min")
OUT_STEM = f"hype_30m_keltner_v3_latest_audit_{RUN_DATE}"
SUMMARY_PATH = base.ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = base.ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = base.ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
WINDOWS = {
    "1d": pd.Timedelta(days=1),
    "7d": pd.Timedelta(days=7),
    "1m": pd.Timedelta(days=30),
    "3m": pd.Timedelta(days=90),
    "6m": pd.Timedelta(days=180),
    "1y": pd.Timedelta(days=365),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-funding", action="store_true")
    parser.add_argument("--timeout", type=float, default=45.0)
    return parser.parse_args()


def load_standard_15m() -> tuple[pd.DataFrame, dict[str, Any]]:
    warehouse = source15.DuckDBWarehouse(
        source15.DataLakeLayout.from_settings(source15.load_settings(None))
    )
    audited, _, quality = source15.load_data(warehouse)
    if quality["blocker_count"]:
        raise RuntimeError(f"15m standard data quality failed: {quality}")
    frame = warehouse.load_dataset(
        layer="normalized",
        kind=source15.DatasetKind.OHLCV,
        exchange=source15.EXCHANGE,
        market_type=source15.MarketType.PERP,
        symbol=source15.SYMBOL,
        timeframe=source15.TIMEFRAME,
        columns=[
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "trade_count",
        ],
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = (
        frame.sort_values("ts")
        .drop_duplicates("ts", keep="last")
        .set_index("ts")
    )
    if not frame.index.equals(audited.index):
        raise RuntimeError("extended 15m frame does not match audited index")
    for column in ("open", "high", "low", "close", "volume"):
        if not frame[column].equals(audited[column]):
            raise RuntimeError(f"extended 15m frame mismatch: {column}")
    return frame.reset_index(), quality


def extend_with_binance_15m(
    source: pd.DataFrame,
    *,
    timeout: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """用小范围 API 尾部补齐，并对标准数据重叠区逐字段核对。"""
    source = source.copy()
    source["ts"] = pd.to_datetime(source["ts"], utc=True)
    server_ms = base.server_time_ms(timeout)
    server_ts = pd.to_datetime(server_ms, unit="ms", utc=True)
    expected_latest = server_ts.floor("15min") - pd.Timedelta(minutes=15)
    overlap_start = source["ts"].max() - pd.Timedelta(hours=1)
    payload = base.request_json(
        base.KLINES_PATH,
        params={
            "symbol": base.SYMBOL,
            "interval": "15m",
            "startTime": int(overlap_start.timestamp() * 1000),
            "endTime": server_ms,
            "limit": 1000,
        },
        timeout=timeout,
    )
    if not isinstance(payload, list) or not payload:
        raise RuntimeError("Binance returned no 15m tail klines")
    tail = pd.DataFrame(
        payload,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trade_count",
            "taker_buy_volume",
            "taker_buy_quote_volume",
            "ignore",
        ],
    )
    tail["ts"] = pd.to_datetime(tail["open_time"], unit="ms", utc=True)
    tail["close_time"] = pd.to_datetime(tail["close_time"], unit="ms", utc=True)
    tail = tail.loc[tail["close_time"] < server_ts].copy()
    value_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
    ]
    for column in value_columns:
        tail[column] = pd.to_numeric(tail[column], errors="coerce")
    tail = (
        tail[["ts", *value_columns]]
        .sort_values("ts")
        .drop_duplicates("ts", keep="last")
        .reset_index(drop=True)
    )
    if tail.empty or tail[value_columns].isna().any().any():
        raise RuntimeError("Binance 15m tail contains no closed bars or null values")

    overlap = source[["ts", *value_columns]].merge(
        tail,
        on="ts",
        how="inner",
        suffixes=("_standard", "_api"),
    )
    if overlap.empty:
        raise RuntimeError("Binance 15m tail has no overlap with standard data")
    mismatch_cells: dict[str, int] = {}
    for column in value_columns:
        left = overlap[f"{column}_standard"].to_numpy("float64")
        right = overlap[f"{column}_api"].to_numpy("float64")
        mismatch_cells[column] = int(
            (~np.isclose(left, right, rtol=0.0, atol=1e-12)).sum()
        )
    if sum(mismatch_cells.values()):
        raise RuntimeError(
            f"Binance 15m tail differs from standard data: {mismatch_cells}"
        )

    standard_end = source["ts"].max()
    additions = tail.loc[tail["ts"] > standard_end, ["ts", *value_columns]]
    extended = (
        pd.concat([source, additions], ignore_index=True)
        .sort_values("ts")
        .drop_duplicates("ts", keep="last")
        .reset_index(drop=True)
    )
    expected = pd.date_range(
        extended["ts"].min(),
        extended["ts"].max(),
        freq="15min",
    )
    missing = expected.difference(pd.DatetimeIndex(extended["ts"]))
    latest = extended["ts"].max()
    if len(missing) or latest != expected_latest:
        raise RuntimeError(
            "Extended 15m tail is incomplete: "
            f"missing={len(missing)} latest={latest} "
            f"expected_latest={expected_latest}"
        )
    return extended, {
        "source": "binance_futures_kline_api",
        "server_time": str(server_ts),
        "standard_end": str(standard_end),
        "latest_closed_bar": str(latest),
        "expected_latest_closed_bar": str(expected_latest),
        "overlap_rows": int(len(overlap)),
        "overlap_mismatch_cells": mismatch_cells,
        "added_rows": int(len(additions)),
        "missing_bars_after_extension": int(len(missing)),
    }


def v3_features(
    source: pd.DataFrame,
    *,
    rows_per_30m: int,
    rows_per_1h: int,
) -> tuple[pd.DataFrame, base.StrategyConfig, dict[str, Any]]:
    b30, q30 = base.aggregate_ohlcv(
        source,
        freq="30min",
        phase_min=0,
        expected_rows=rows_per_30m,
    )
    h1, q1h = base.aggregate_ohlcv(
        source,
        freq="60min",
        phase_min=0,
        expected_rows=rows_per_1h,
    )
    config = dynamic.v21_config()
    features = dynamic.v21_features(b30, h1, config)
    filter_spec = regime.FilterSpec(
        "combo",
        "pair",
        (),
        (
            regime.FilterSpec("volatility", "atr_pct", (0.0, 0.0125)),
            regime.FilterSpec("quality", "close_location", (0.65,)),
        ),
    )
    features = regime.apply_filter(regime.add_features(features), filter_spec)
    return features, config, {"30m": q30, "1h": q1h}


def load_frozen_1m_reference() -> tuple[pd.DataFrame, dict[str, Any]]:
    if not base.CACHE_PATH.exists():
        raise FileNotFoundError(base.CACHE_PATH)
    frame = pd.read_parquet(base.CACHE_PATH)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = (
        frame.loc[frame["ts"] < FROZEN_UNTIL]
        .sort_values("ts")
        .drop_duplicates("ts", keep="last")
        .reset_index(drop=True)
    )
    quality = base.data_quality(frame)
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
        raise RuntimeError(f"frozen 1m reference quality failed: {quality}")
    return frame, quality


def input_parity(
    reference: pd.DataFrame,
    candidate: pd.DataFrame,
    reference_trades: pd.DataFrame,
    candidate_trades: pd.DataFrame,
) -> dict[str, Any]:
    common_index = reference.index.intersection(candidate.index)
    value_mismatches: dict[str, int] = {}
    max_abs_diff: dict[str, float] = {}
    for column in ("open", "high", "low", "close"):
        left = reference.loc[common_index, column].to_numpy("float64")
        right = candidate.loc[common_index, column].to_numpy("float64")
        value_mismatches[column] = int(
            (~np.isclose(left, right, rtol=0.0, atol=1e-12)).sum()
        )
        max_abs_diff[column] = float(
            np.max(np.abs(left - right)) if len(left) else 0.0
        )
    trade_columns = ["direction", "entry_ts", "exit_ts", "exit_reason"]
    left_trades = reference_trades[trade_columns].copy().reset_index(drop=True)
    right_trades = candidate_trades[trade_columns].copy().reset_index(drop=True)
    for frame in (left_trades, right_trades):
        frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
        frame["exit_ts"] = pd.to_datetime(frame["exit_ts"], utc=True)
    differing_rows = left_trades.ne(right_trades).any(axis=1)
    trade_paths_equal = bool(
        len(left_trades) == len(right_trades)
        and not differing_rows.any()
    )
    first_differences = [
        {
            "row": int(idx),
            "reference": left_trades.loc[idx].to_dict(),
            "candidate": right_trades.loc[idx].to_dict(),
        }
        for idx in differing_rows.loc[differing_rows].index[:5]
    ]
    return {
        "common_30m_bars": int(len(common_index)),
        "ohlc_mismatch_cells": value_mismatches,
        "ohlc_max_abs_diff": max_abs_diff,
        "trade_paths_equal": trade_paths_equal,
        "reference_trades": int(len(left_trades)),
        "candidate_trades": int(len(right_trades)),
        "first_trade_path_differences": first_differences,
    }


def sliced_metrics(
    result: strict.StrictResult,
    *,
    start: pd.Timestamp,
    label: str,
) -> dict[str, Any]:
    start = pd.Timestamp(start)
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    else:
        start = start.tz_convert("UTC")
    end = result.equity.index.max()
    selected = result.equity.loc[result.equity.index >= start]
    before = result.equity.loc[result.equity.index < start]
    if selected.empty:
        return {
            "label": label,
            "start": str(start),
            "end": str(end),
            "return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "closed_trades": 0,
            "win_rate_pct": 0.0,
        }
    base_equity = float(before.iloc[-1]) if not before.empty else 1.0
    anchored = pd.concat(
        [
            pd.Series(
                [base_equity],
                index=[selected.index[0] - pd.Timedelta(minutes=30)],
            ),
            selected,
        ]
    )
    drawdown = anchored / anchored.cummax() - 1.0
    trades = result.trades
    selected_trades = (
        trades.loc[
            pd.to_datetime(trades["exit_ts"], utc=True).between(
                start,
                end,
                inclusive="both",
            )
        ]
        if not trades.empty
        else trades
    )
    trade_returns = pd.to_numeric(
        selected_trades.get("net_account_return_pct"),
        errors="coerce",
    )
    return {
        "label": label,
        "start": str(selected.index.min()),
        "end": str(end),
        "return_pct": float(
            (float(selected.iloc[-1]) / base_equity - 1.0) * 100.0
        ),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "closed_trades": int(len(selected_trades)),
        "win_rate_pct": (
            float(trade_returns.gt(0.0).mean() * 100.0)
            if len(selected_trades)
            else 0.0
        ),
    }


def recent_slices(result: strict.StrictResult) -> list[dict[str, Any]]:
    end = result.equity.index.max()
    return [
        sliced_metrics(
            result,
            start=end - delta,
            label=label,
        )
        for label, delta in WINDOWS.items()
    ]


def side_metrics(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {}
    output: dict[str, Any] = {}
    for direction, frame in trades.groupby("direction", sort=True):
        returns = pd.to_numeric(
            frame["net_account_return_pct"],
            errors="coerce",
        )
        wins = returns.loc[returns > 0.0]
        losses = returns.loc[returns < 0.0]
        output[str(direction)] = {
            "trades": int(len(frame)),
            "win_rate_pct": float(returns.gt(0.0).mean() * 100.0),
            "sum_trade_return_pct": float(returns.sum()),
            "profit_factor": (
                float(wins.sum() / -losses.sum())
                if float(-losses.sum()) > 0.0
                else None
            ),
        }
    return output


def serialize_result(result: strict.StrictResult) -> dict[str, Any]:
    return {
        "metrics": result.metrics,
        "slices": recent_slices(result),
        "side_metrics": side_metrics(result.trades),
        "diagnostics": result.diagnostics,
    }


def main() -> None:
    args = parse_args()
    base.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    source, data_audit = load_standard_15m()
    source, tail_refresh = extend_with_binance_15m(
        source,
        timeout=args.timeout,
    )
    features, config, aggregation = v3_features(
        source,
        rows_per_30m=2,
        rows_per_1h=4,
    )
    frozen_1m, frozen_1m_quality = load_frozen_1m_reference()
    reference_features, reference_config, reference_aggregation = v3_features(
        frozen_1m,
        rows_per_30m=30,
        rows_per_1h=60,
    )
    funding_args = type(
        "FundingArgs",
        (),
        {"refresh_data": args.refresh_funding, "timeout": args.timeout},
    )()
    funding = strict.load_or_fetch_funding(funding_args, source)
    execution = strict.ExecutionConfig()
    ready_start = strict.ready_start(features)
    end = features.index.max() + pd.Timedelta(minutes=30)

    frozen_reference = strict.simulate(
        "v3_frozen_1m_reference",
        reference_features,
        funding,
        reference_config,
        execution,
        start_ts=strict.ready_start(reference_features),
        end_ts=FROZEN_UNTIL,
        force_close=True,
    )
    frozen_effective_end = (
        reference_features.index.max() + pd.Timedelta(minutes=30)
    )
    if frozen_reference.metrics["trades"] != 78:
        raise RuntimeError(
            f"V3 frozen reference trade parity failed: "
            f"{frozen_reference.metrics}"
        )
    if (
        abs(float(frozen_reference.metrics["return_pct"]) - 6328.98)
        > 0.10
    ):
        raise RuntimeError(
            f"V3 frozen reference return parity failed: "
            f"{frozen_reference.metrics}"
        )

    frozen_cross_input = strict.simulate(
        "v3_frozen_15m_cross_input",
        features,
        funding,
        config,
        execution,
        start_ts=ready_start,
        end_ts=frozen_effective_end,
        force_close=True,
    )
    parity = input_parity(
        reference_features,
        features.loc[features.index < frozen_effective_end],
        frozen_reference.trades,
        frozen_cross_input.trades,
    )
    if not parity["trade_paths_equal"]:
        raise RuntimeError(f"V3 cross-input trade paths differ: {parity}")

    latest = strict.simulate(
        "v3_latest_full",
        features,
        funding,
        config,
        execution,
        start_ts=ready_start,
        end_ts=end,
        force_close=False,
    )
    prospective = strict.simulate(
        "v3_clean_prospective",
        features,
        funding,
        config,
        execution,
        start_ts=PROSPECTIVE_START,
        end_ts=end,
        force_close=False,
    )
    continuation = sliced_metrics(
        latest,
        start=PROSPECTIVE_START,
        label="frozen_continuation",
    )
    new_entries = (
        latest.trades.loc[
            pd.to_datetime(latest.trades["entry_ts"], utc=True)
            >= FROZEN_UNTIL
        ]
        if not latest.trades.empty
        else latest.trades
    )
    payload = {
        "family": "HYPE-30M-Keltner-Trend-Breakout",
        "version": "HYPE-30M-Keltner-Trend-Breakout-V3",
        "status": "registered / not promoted / not live-ready",
        "run_date": RUN_DATE,
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "purpose": (
            "Frozen-parameter latest validity and prospective extension audit; "
            "no parameter search and no status promotion."
        ),
        "frozen_until": str(FROZEN_UNTIL),
        "prospective_first_30m_bar_label": str(PROSPECTIVE_START),
        "data": {
            "source_timeframe": "15m",
            "source_note": (
                "Audited standard 15m bars aggregated losslessly to complete "
                "30m/1h bars; frozen 1m-input metrics must pass exact parity."
            ),
            "start": str(pd.to_datetime(source["ts"], utc=True).min()),
            "end": str(pd.to_datetime(source["ts"], utc=True).max()),
            "rows": int(len(source)),
            "audit": data_audit,
            "tail_refresh": tail_refresh,
            "aggregation": aggregation,
        },
        "frozen_1m_reference": {
            "quality": frozen_1m_quality,
            "aggregation": reference_aggregation,
        },
        "funding": {
            "rows": int(len(funding)),
            "start": str(funding["ts"].min()) if len(funding) else None,
            "end": str(funding["ts"].max()) if len(funding) else None,
            "null_rates": (
                int(funding["funding_rate"].isna().sum())
                if len(funding)
                else 0
            ),
        },
        "strategy_config": asdict(config),
        "execution_config": asdict(execution),
        "frozen_reference_parity": serialize_result(frozen_reference),
        "frozen_cross_input": {
            **serialize_result(frozen_cross_input),
            "parity": parity,
            "return_difference_pp": float(
                frozen_cross_input.metrics["return_pct"]
                - frozen_reference.metrics["return_pct"]
            ),
        },
        "latest_full": serialize_result(latest),
        "frozen_continuation": continuation,
        "clean_prospective": serialize_result(prospective),
        "new_closed_trades_after_freeze": int(len(new_entries)),
        "known_unchanged_blockers": [
            "30m non-native phase gate failed",
            "15m/1h/2h timeframe transfer failed",
            "close-location risk contribution not proven",
            "live-executable runner parity not completed",
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    trade_frames = []
    for scope, frame in (
        ("latest_full", latest.trades),
        ("clean_prospective", prospective.trades),
    ):
        output = frame.copy()
        output.insert(0, "scope", scope)
        trade_frames.append(output)
    pd.concat(trade_frames, ignore_index=True).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [
            latest.equity.rename("latest_full"),
            prospective.equity.rename("clean_prospective"),
        ],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data {payload['data']['start']} -> {payload['data']['end']} "
        f"rows={payload['data']['rows']} "
        f"quality={data_audit['blocker_count'] == 0}"
    )
    print("frozen 1m reference", frozen_reference.metrics)
    print("frozen 15m cross-input", frozen_cross_input.metrics)
    print("input parity", parity)
    print("latest full", latest.metrics)
    print("frozen continuation", continuation)
    print("clean prospective", prospective.metrics)
    print("recent", recent_slices(latest))
    print("new closed trades", len(new_entries))
    print("summary", SUMMARY_PATH)


if __name__ == "__main__":
    main()
