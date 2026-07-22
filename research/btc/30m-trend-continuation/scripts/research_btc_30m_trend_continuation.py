from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/30m-trend-continuation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SOURCE_PATH = (
    ROOT
    / "research/btc/15m-trend-continuation/scripts"
    / "research_btc_15m_low_vol_compression_breakout.py"
)
SOURCE_SHA256 = "581326b35f376a4e5d397bd8255dad0425eab763939f707f5ed1eaf7b1c3c026"
SOURCE_15M_AUDIT = (
    ROOT
    / "research/btc/15m-trend-continuation/artifacts"
    / "btc_binance_15m_long_data_quality_latest.json"
)
DATE = "2026-07-21"
SUMMARY_PATH = ARTIFACT_DIR / f"btc_30m_tc_summary_{DATE}.json"
CANDIDATES_PATH = ARTIFACT_DIR / f"btc_30m_tc_candidates_{DATE}.csv"
TRADES_PATH = ARTIFACT_DIR / f"btc_30m_tc_selected_trades_{DATE}.csv"
WINDOWS_PATH = ARTIFACT_DIR / f"btc_30m_tc_rolling_windows_{DATE}.csv"
OHLCV_30M_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=30m"
)
OHLCV_15M_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
SYMBOL_FILE = "symbol=btc_usdt_usdt.parquet"
BAR = pd.Timedelta(minutes=30)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_source() -> Any:
    actual = sha256_bytes(SOURCE_PATH.read_bytes())
    if actual != SOURCE_SHA256:
        raise RuntimeError(
            "BTC LVCB research source SHA mismatch: "
            f"expected {SOURCE_SHA256}, got {actual}"
        )
    module_name = "btc_30m_trend_continuation_source"
    spec = importlib.util.spec_from_file_location(module_name, SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load research source: {SOURCE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def configure(source: Any) -> None:
    source.FAMILY_DIR = FAMILY_DIR
    source.ARTIFACT_DIR = ARTIFACT_DIR
    source.AUDIT_PATH = ARTIFACT_DIR / "btc_binance_30m_long_data_quality_latest.json"
    source.OHLCV_ROOT = OHLCV_30M_ROOT
    source.DATE = DATE
    source.CANDIDATES_PATH = CANDIDATES_PATH
    source.SUMMARY_PATH = SUMMARY_PATH
    source.TRADES_PATH = TRADES_PATH
    source.WINDOWS_PATH = WINDOWS_PATH
    source.BAR = BAR

    # Preserve the 15m search's wall-clock horizons after changing bar size.
    source.COMPRESSION_QUANTILES = (0.25, 0.30, 0.35, 0.40)
    source.COMPRESSION_LOOKBACKS = (8, 16, 32)
    source.BREAKOUT_WINDOWS = (48, 96)
    source.EMA_PAIRS = ((48, 192),)
    source.SLOPE_LAGS = (8,)
    source.ATR_CAPS = (0.00325, 0.00350, 0.00375, 0.00400, 0.00425)
    source.EXIT_PROFILES = tuple(
        (stop_atr, hold_bars)
        for stop_atr in (3.0, 4.0, 5.0)
        for hold_bars in (48, 96, 192)
    )
    source.load_data = lambda: load_30m_data(source)


def load_30m_data(source: Any) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    audit = json.loads(source.AUDIT_PATH.read_text(encoding="utf-8"))
    if audit.get("total_blocker_count") != 0:
        raise RuntimeError("BTC 30m long-history audit has blockers")
    start = pd.Timestamp(audit["research_start"])
    end = pd.Timestamp(audit["closed_bar_cutoff_exclusive"])
    market_columns = [
        "ts",
        "exchange",
        "symbol",
        "market_type",
        "timeframe",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "is_closed",
        "source",
    ]
    market = pd.concat(
        [
            pd.read_parquet(path, columns=market_columns)
            for path in source.date_paths(source.OHLCV_ROOT, start, end)
        ],
        ignore_index=True,
    )
    market["ts"] = pd.to_datetime(market["ts"], utc=True)
    market = (
        market.loc[(market["ts"] >= start) & (market["ts"] < end)]
        .sort_values("ts")
        .reset_index(drop=True)
    )
    funding_columns = ["ts", "funding_rate", "source"]
    funding = pd.concat(
        [
            pd.read_parquet(path, columns=funding_columns)
            for path in source.date_paths(source.FUNDING_ROOT, start, end)
        ],
        ignore_index=True,
    )
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = (
        funding.loc[(funding["ts"] >= start) & (funding["ts"] < end)]
        .sort_values("ts")
        .reset_index(drop=True)
    )
    expected = pd.date_range(start, end - BAR, freq=BAR)
    checks = {
        "market_rows": len(market) == len(expected),
        "market_continuity": pd.DatetimeIndex(market["ts"]).equals(expected),
        "market_duplicates": not market["ts"].duplicated().any(),
        "market_closed": bool(market["is_closed"].all()),
        "market_identity": bool(
            market["exchange"].eq("binance").all()
            and market["symbol"].eq("BTC/USDT:USDT").all()
            and market["market_type"].eq("perp").all()
            and market["timeframe"].eq("30m").all()
        ),
        "market_nulls": not market[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
                "vwap",
            ]
        ]
        .isna()
        .any()
        .any(),
        "funding_nonempty": not funding.empty,
        "funding_duplicates": not funding["ts"].duplicated().any(),
        "funding_gap": bool(
            funding["ts"].diff().dropna().max() <= pd.Timedelta(hours=8)
        ),
        "funding_nulls": not funding[["ts", "funding_rate", "source"]]
        .isna()
        .any()
        .any(),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"BTC 30m trend data checks failed: {failed}")
    metadata = {
        "audit_path": str(source.AUDIT_PATH.relative_to(ROOT)),
        "audit_sha256": sha256_bytes(source.AUDIT_PATH.read_bytes()),
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "market_rows": len(market),
        "funding_rows": len(funding),
        "checks": checks,
    }
    return market.set_index("ts"), funding, metadata


def load_15m_phase_source(
    source: Any,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    audit = json.loads(SOURCE_15M_AUDIT.read_text(encoding="utf-8"))
    if audit.get("total_blocker_count") != 0:
        raise RuntimeError("BTC 15m source audit has blockers")
    audit_start = pd.Timestamp(audit["research_start"])
    audit_end = pd.Timestamp(audit["closed_bar_cutoff_exclusive"])
    if audit_start > start or audit_end < end:
        raise RuntimeError("BTC 15m source does not cover the native 30m audit range")
    paths = source.date_paths(OHLCV_15M_ROOT, start, end)
    columns = [
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
    ]
    frame = pd.concat(
        [pd.read_parquet(path, columns=columns) for path in paths],
        ignore_index=True,
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.loc[(frame["ts"] >= start) & (frame["ts"] < end)]
    frame = frame.sort_values("ts").drop_duplicates("ts", keep=False).set_index("ts")
    expected = pd.date_range(start, end - pd.Timedelta(minutes=15), freq="15min")
    if not frame.index.equals(expected):
        raise RuntimeError("BTC 15m phase source is not continuous")
    return frame


def aggregate_offset_30m(frame: pd.DataFrame) -> pd.DataFrame:
    grouper = frame.resample(
        "30min",
        origin="start_day",
        offset="15min",
        closed="left",
        label="left",
    )
    counts = grouper["close"].count()
    output = grouper.agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "quote_volume": "sum",
            "trade_count": "sum",
        }
    )
    output = output.loc[counts == 2].copy()
    output["vwap"] = output["quote_volume"] / output["volume"].replace(0.0, pd.NA)
    if output.empty:
        raise RuntimeError("offset 30m aggregation produced no complete bars")
    expected = pd.date_range(output.index[0], output.index[-1], freq="30min")
    if not output.index.equals(expected):
        raise RuntimeError("offset 30m aggregation is not continuous")
    return output


def metrics_for_range(
    source: Any,
    frame: pd.DataFrame,
    funding_path: Any,
    atr: Any,
    signals: tuple[Any, Any],
    config: Any,
    start: pd.Timestamp,
    end: pd.Timestamp,
    label: str,
) -> dict[str, Any]:
    return source.simulate(
        frame,
        funding_path,
        atr,
        signals[0],
        signals[1],
        config,
        start,
        end,
        label=label,
    ).metrics


def phase_audit(
    source: Any,
    summary: dict[str, Any],
    funding: pd.DataFrame,
) -> dict[str, Any]:
    start = pd.Timestamp(summary["data"]["start"])
    native_end = pd.Timestamp(summary["data"]["end_exclusive"])
    phase_source = load_15m_phase_source(source, start, native_end)
    frame = aggregate_offset_30m(phase_source)
    phase_end = frame.index[-1] + BAR
    features = source.base_features(frame)
    atr = features["atr"].to_numpy(float)
    funding_path = source.funding_cumulative(frame.index, funding)

    selected = summary["selected"]["config"]
    config = source.StrategyConfig(
        signal=source.SignalConfig(**selected["signal"]),
        stop_atr=selected["stop_atr"],
        max_hold_bars=selected["max_hold_bars"],
        side_mode=selected["side_mode"],
        fee_per_fill=selected["fee_per_fill"],
        slippage_per_fill=selected["slippage_per_fill"],
    )
    signals = source.build_signals(frame, features, config.signal)
    ranges = {
        "train": (source.TRAIN_START, source.VALIDATION_START),
        "validation": (source.VALIDATION_START, source.DIAGNOSTIC_START),
        "reused_diagnostic": (source.DIAGNOSTIC_START, phase_end),
    }
    metrics = {
        name: metrics_for_range(
            source,
            frame,
            funding_path,
            atr,
            signals,
            config,
            range_start,
            range_end,
            f"phase15_{name}",
        )
        for name, (range_start, range_end) in ranges.items()
    }
    stress = replace(
        config,
        fee_per_fill=source.FEE_PER_FILL * 2.0,
        slippage_per_fill=source.SLIPPAGE_PER_FILL * 2.0,
    )
    metrics["reused_diagnostic_2x_cost"] = metrics_for_range(
        source,
        frame,
        funding_path,
        atr,
        signals,
        stress,
        source.DIAGNOSTIC_START,
        phase_end,
        "phase15_reused_diagnostic_2x",
    )
    metrics["recent_slices"] = source.recent_slices(
        frame,
        funding_path,
        atr,
        signals,
        config,
        phase_end,
    )
    phase_gate_pass = all(
        metrics[name]["return_pct"] > 0.0
        for name in (
            "train",
            "validation",
            "reused_diagnostic",
            "reused_diagnostic_2x_cost",
        )
    )
    return {
        "purpose": (
            "Audit sensitivity to a 15-minute shift of the 30m candle boundary; "
            "this is robustness evidence, not untouched OOS."
        ),
        "source_timeframe": "audited native 15m",
        "aggregation": (
            "left-closed 30m OHLCV groups at hh:15/hh:45; require exactly two "
            "source bars; OHLC first/max/min/last; additive volume fields"
        ),
        "range": [frame.index[0].isoformat(), phase_end.isoformat()],
        "bar_count": len(frame),
        "metrics": metrics,
        "phase_gate_pass": phase_gate_pass,
        "provenance": {
            "source_dataset_identity": (
                "Binance USD-M Futures BTCUSDT perpetual native 15m normalized "
                "data-lake partitions"
            ),
            "source_audit_path": str(SOURCE_15M_AUDIT.relative_to(ROOT)),
            "source_audit_sha256": sha256_bytes(SOURCE_15M_AUDIT.read_bytes()),
            "derivation_formula_version": "btc-30m-offset15-ohlcv-v1",
            "source_columns": [
                "ts",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
            ],
            "generation_time_utc": datetime.now(timezone.utc).isoformat(),
            "null_policy": "drop any 30m group without exactly two 15m bars",
            "fill_policy": "none",
            "code_path": str(Path(__file__).resolve().relative_to(ROOT)),
            "code_sha256": sha256_bytes(Path(__file__).read_bytes()),
        },
    }


def correct_summary(
    source: Any,
    summary: dict[str, Any],
    phase: dict[str, Any],
) -> dict[str, Any]:
    summary["family"] = "BTC-30M-Trend-Continuation"
    summary["research_identity"] = "BTC-30M-TC-LONG-HISTORY-SEARCH-2026-07-21"
    summary["execution"]["entry"] = "closed native 30m signal, next native 30m open"
    summary["execution"]["time_exit"] = "max_hold reached at 30m bar open"
    summary["phase_alignment_audit"] = phase
    summary["research_role"] = (
        "full-history research candidate; prospective OOS required"
        if summary["research_candidate"] and phase["phase_gate_pass"]
        else "failed diagnostic"
    )
    summary["research_candidate"] = bool(
        summary["research_candidate"] and phase["phase_gate_pass"]
    )
    summary["remaining_blockers"] = [
        "no untouched historical OOS; prospective evidence begins at frozen end",
        "CPCV and live-executable runner audit not completed",
        "absolute ATR cap requires forward stability monitoring",
    ]
    script_path = Path(__file__).resolve()
    summary["provenance"].update(
        {
            "formula_version": "btc-30m-trend-continuation-v1-search",
            "code_path": str(script_path.relative_to(ROOT)),
            "code_sha256": sha256_bytes(script_path.read_bytes()),
            "engine_path": str(SOURCE_PATH.relative_to(ROOT)),
            "engine_sha256": SOURCE_SHA256,
        }
    )
    return summary


def main() -> None:
    source = load_source()
    configure(source)
    source.main()
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    _, funding, _ = source.load_data()
    phase = phase_audit(source, summary, funding)
    summary = correct_summary(source, summary, phase)
    source.atomic_write_json(SUMMARY_PATH, summary)
    print(
        json.dumps(
            {
                "research_candidate": summary["research_candidate"],
                "selected_strategy_id": summary["selected"]["strategy_id"],
                "selected": summary["selected"],
                "reused_diagnostic": summary["reused_diagnostic"],
                "reused_diagnostic_2x_cost": summary["reused_diagnostic_2x_cost"],
                "recent_slices": summary["recent_slices"],
                "phase_alignment_audit": summary["phase_alignment_audit"],
                "year_metrics": summary["year_metrics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
