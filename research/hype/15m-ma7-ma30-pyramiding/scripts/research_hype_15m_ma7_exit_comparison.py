from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-ma7-ma30-pyramiding"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
MA_SCRIPT = ROOT / "research/hype/1d-pyramiding-trend/scripts/research_hype_1d_ma7_ma30.py"
MA_SCRIPT_SHA256 = "6a3517c4cc066a1678881c2a1d1fa34bf6b4a98f8fd336e71abd50ec214c6b42"
SOURCE_FRAME = (
    ROOT / "research/hype/15m-ema-trend-breakout/artifacts"
    / "hype_binance_15m_closed_klines.parquet"
)
SOURCE_QUALITY = (
    ROOT / "research/hype/15m-ema-trend-breakout/artifacts"
    / "hype_binance_15m_data_quality.json"
)
FUNDING_ROOT = (
    ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
)
PREFIT_END = pd.Timestamp("2026-04-30T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare HYPE 15m opposite-cross and MA7 exits.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_ma_module() -> object:
    digest = hashlib.sha256(MA_SCRIPT.read_bytes()).hexdigest()
    if digest != MA_SCRIPT_SHA256:
        raise RuntimeError(
            f"HYPE MA7/MA30 engine drift: expected {MA_SCRIPT_SHA256}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location("hype_15m_ma7_exit_engine", MA_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {MA_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def frozen_control(ma: object) -> object:
    return ma.Config(
        ma_type=1,
        entry_mode=2,
        direction=0,
        confirm_days=2,
        slope_days=1,
        breakout_window=7,
        entry_buffer_atr=0.0,
        exit_mode=0,
        atr_window=10,
        adx_min=0.0,
        atr_pct_cap=0.0,
        initial_leverage=0.5,
        add_mode=1,
        add_step_atr=0.25,
        add_increment=1.5,
        stop_atr=3.0,
        trail_atr=3.0,
        profit_trigger_atr=3.0,
        profit_lock_atr=0.5,
        max_hold_days=20,
        cooldown_days=2,
        allow_flip=False,
    )


def stable_target_quantity(
    equity: float,
    old_qty: float,
    target_leverage: float,
    price: float,
    cost_rate: float,
) -> tuple[float, float, float]:
    old_notional = old_qty * price
    candidate_above = (
        (equity + cost_rate * old_notional)
        / (1.0 + cost_rate * target_leverage)
    )
    signed_turnover_above = target_leverage * candidate_above - old_notional
    if signed_turnover_above >= -1e-12:
        post_equity = candidate_above
    else:
        post_equity = (
            (equity - cost_rate * old_notional)
            / (1.0 - cost_rate * target_leverage)
        )
    target_qty = target_leverage * post_equity / price
    turnover = abs(target_qty - old_qty) * price
    reconciled = equity - turnover * cost_rate
    if not math.isclose(reconciled, post_equity, rel_tol=1e-12, abs_tol=1e-15):
        raise RuntimeError("post-cost target sizing reconciliation failed")
    return target_qty, reconciled, turnover


def load_and_audit() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    metadata = json.loads(SOURCE_QUALITY.read_text(encoding="utf-8"))
    upstream = metadata["data_quality"]
    if int(upstream["blocker_count"]) != 0:
        raise RuntimeError(f"upstream HYPE 15m blockers: {upstream}")
    frame = pd.read_parquet(SOURCE_FRAME)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    expected = pd.date_range(frame["ts"].iloc[0], frame["ts"].iloc[-1], freq="15min")
    required = [
        "ts", "open", "high", "low", "close", "volume", "quote_volume",
        "trade_count", "vwap", "is_closed", "source",
    ]
    missing_columns = sorted(set(required).difference(frame.columns))
    nulls = {column: int(frame[column].isna().sum()) for column in required if column in frame}
    invalid_ohlc = int(
        (
            (frame[["open", "high", "low", "close"]] <= 0.0).any(axis=1)
            | frame["high"].lt(frame[["open", "close", "low"]].max(axis=1))
            | frame["low"].gt(frame[["open", "close", "high"]].min(axis=1))
        ).sum()
    )
    quality = {
        "rows": int(len(frame)),
        "first_ts": frame["ts"].iloc[0].isoformat(),
        "last_ts": frame["ts"].iloc[-1].isoformat(),
        "expected_rows": int(len(expected)),
        "missing_bars": int(len(expected.difference(pd.DatetimeIndex(frame["ts"])))),
        "duplicate_ts": int(frame["ts"].duplicated().sum()),
        "critical_nulls": nulls,
        "invalid_ohlc_rows": invalid_ohlc,
        "non_closed_rows": int((~frame["is_closed"].astype(bool)).sum()),
        "upstream_raw_normalized_mismatch": upstream["raw_normalized_mismatch"],
        "upstream_blocker_count": int(upstream["blocker_count"]),
    }
    quality["blocker_count"] = int(
        len(missing_columns)
        + quality["missing_bars"]
        + quality["duplicate_ts"]
        + sum(nulls.values())
        + invalid_ohlc
        + quality["non_closed_rows"]
        + sum(int(value) for value in upstream["raw_normalized_mismatch"].values())
    )
    if quality["blocker_count"]:
        raise RuntimeError(f"HYPE 15m blockers: {quality}")

    funding_files = sorted(FUNDING_ROOT.glob("date=*/symbol=hype_usdt_usdt.parquet"))
    if not funding_files:
        raise FileNotFoundError(f"no HYPE funding under {FUNDING_ROOT}")
    funding = pd.concat([pd.read_parquet(path) for path in funding_files], ignore_index=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding["funding_rate"] = pd.to_numeric(funding["funding_rate"], errors="coerce")
    funding = funding.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    gaps = funding["ts"].diff().dropna()
    funding_quality = {
        "rows": int(len(funding)),
        "first_ts": funding["ts"].iloc[0].isoformat(),
        "last_ts": funding["ts"].iloc[-1].isoformat(),
        "duplicate_ts_after_dedup": int(funding["ts"].duplicated().sum()),
        "critical_null_rows": int(funding[["ts", "funding_rate"]].isna().any(axis=1).sum()),
        "max_gap_hours": float(gaps.max().total_seconds() / 3600.0),
    }
    funding_quality["blocker_count"] = int(
        funding_quality["duplicate_ts_after_dedup"]
        + funding_quality["critical_null_rows"]
        + (funding_quality["max_gap_hours"] > 8.01)
    )
    if funding_quality["blocker_count"]:
        raise RuntimeError(f"HYPE funding blockers: {funding_quality}")
    quality["funding"] = funding_quality
    return frame, funding[["ts", "funding_rate"]].copy(), quality


def build_book(ma: object) -> object:
    parent = ma._load_parent()
    frame, funding, quality = load_and_audit()
    if len(frame) < 2:
        raise RuntimeError("need at least two closed 15m bars")
    terminal_row = frame.iloc[-1]
    bars = frame.iloc[:-1].copy()
    terminal_ts = pd.Timestamp(terminal_row["ts"])
    open_values = bars["open"].to_numpy("float64")
    high = bars["high"].to_numpy("float64")
    low = bars["low"].to_numpy("float64")
    close = bars["close"].to_numpy("float64")
    open_index = pd.DatetimeIndex([*bars["ts"], terminal_ts])
    quality["research_rows"] = int(len(bars))
    quality["research_first_ts"] = bars["ts"].iloc[0].isoformat()
    quality["research_last_ts"] = bars["ts"].iloc[-1].isoformat()
    quality["terminal_open_ts"] = terminal_ts.isoformat()
    quality["terminal_open"] = float(terminal_row["open"])
    return ma.Book(
        ts=pd.DatetimeIndex(bars["ts"]),
        terminal_ts=terminal_ts,
        open=open_values,
        high=high,
        low=low,
        close=close,
        ma7={0: ma._sma(close, 7), 1: ma._ema(close, 7)},
        ma30={0: ma._sma(close, 30), 1: ma._ema(close, 30)},
        atr={window: parent._atr(high, low, close, window) for window in (5, 7, 10, 14, 20, 30)},
        adx={window: parent._adx(high, low, close, window) for window in (5, 7, 10, 14, 20, 30)},
        prior_high={window: parent._prior_roll(high, window, "max") for window in (2, 3, 5, 7, 10, 14, 20)},
        prior_low={window: parent._prior_roll(low, window, "min") for window in (2, 3, 5, 7, 10, 14, 20)},
        funding_by_open=parent._funding_by_open(open_index, funding),
        quality=quality,
        funding_quality=quality["funding"],
    )


def audit_window(ma: object, config: object, book: object, start: int, end: int, retain: bool) -> dict[str, Any]:
    base = ma.backtest(config, book, start_index=start, terminal_index=end, retain=retain)
    stress = ma.backtest(config, book, start_index=start, terminal_index=end, slippage=ma.STRESS_SLIPPAGE)
    delayed = ma.backtest(config, book, start_index=start, terminal_index=end, delay_days=2)
    base_fee = ma.FEE
    try:
        ma.FEE = 0.0
        zero_cost = ma.backtest(
            config,
            book,
            start_index=start,
            terminal_index=end,
            slippage=0.0,
        )
    finally:
        ma.FEE = base_fee
    return {
        "base": base.metrics,
        "stress_8bps": stress.metrics,
        "k_plus_2": delayed.metrics,
        "zero_cost_diagnostic": zero_cost.metrics,
        "recent_slices": ma.recent_slices(base.path) if retain else [],
        "trades": base.trades,
        "path": base.path,
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    raise TypeError(type(value).__name__)


def main() -> None:
    args = parse_args()
    ma = load_ma_module()
    if args.self_test:
        ma.self_test()
        qty, equity, turnover = stable_target_quantity(1.0, 0.0, 3.0, 10.0, 0.0014)
        assert math.isclose(abs(qty) * 10.0 / equity, 3.0, rel_tol=0.0, abs_tol=1e-12)
        assert math.isclose(equity, 1.0 - turnover * 0.0014, rel_tol=0.0, abs_tol=1e-12)
        print("self-test: PASS")
        return
    ma._target_quantity = stable_target_quantity
    book = build_book(ma)
    control = frozen_control(ma)
    variants = {
        "opposite_cross_control": control,
        "close_through_ma7": replace(control, exit_mode=1),
    }
    prefit_end = int(book.ts.searchsorted(PREFIT_END))
    holdout_start = int(book.ts.searchsorted(HOLDOUT_START))
    windows = {
        "prefit": (0, prefit_end),
        "researcher_exposed_holdout_flat": (holdout_start, book.daily_count),
        "full": (0, book.daily_count),
    }
    output: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "HYPE-15M-MA7-MA30-Pyramiding",
        "status": "explore / not promoted / not live-ready",
        "selection": "two exits frozen before outcome; no parameter search",
        "source_engine": {
            "path": str(MA_SCRIPT.relative_to(ROOT)),
            "sha256": MA_SCRIPT_SHA256,
        },
        "data_quality": book.quality,
        "costs": {
            "fee_per_fill": ma.FEE,
            "base_slippage_per_fill": ma.SLIPPAGE,
            "stress_slippage_per_fill": ma.STRESS_SLIPPAGE,
        },
        "variants": {},
    }
    summary_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []
    for name, config in variants.items():
        variant_result: dict[str, Any] = {
            "config": ma.serialize_config(config),
            "windows": {},
        }
        for window, (start, end) in windows.items():
            result = audit_window(ma, config, book, start, end, retain=True)
            variant_result["windows"][window] = {
                key: value for key, value in result.items() if key not in {"trades", "path"}
            }
            summary_rows.append({
                "variant": name,
                "window": window,
                **result["base"],
                "stress_8bps_annualized_factor": result["stress_8bps"]["annualized_factor"],
                "stress_8bps_max_drawdown_pct": result["stress_8bps"]["max_drawdown_pct"],
                "k_plus_2_annualized_factor": result["k_plus_2"]["annualized_factor"],
                "k_plus_2_max_drawdown_pct": result["k_plus_2"]["max_drawdown_pct"],
                "zero_cost_annualized_factor": result["zero_cost_diagnostic"]["annualized_factor"],
                "zero_cost_max_drawdown_pct": result["zero_cost_diagnostic"]["max_drawdown_pct"],
            })
            trade_rows.extend({"variant": name, "window": window, **row} for row in result["trades"])
            path_rows.extend({"variant": name, "window": window, **row} for row in result["path"])
        output["variants"][name] = variant_result

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "hype-15m-ma7-exit-comparison"
    (ARTIFACT_DIR / f"{stem}-summary-{args.run_date}.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    pd.DataFrame(summary_rows).to_csv(ARTIFACT_DIR / f"{stem}-summary-{args.run_date}.csv", index=False)
    pd.DataFrame(trade_rows).to_csv(ARTIFACT_DIR / f"{stem}-trades-{args.run_date}.csv", index=False)
    pd.DataFrame(path_rows).to_csv(ARTIFACT_DIR / f"{stem}-path-{args.run_date}.csv", index=False)
    print(json.dumps(output, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
