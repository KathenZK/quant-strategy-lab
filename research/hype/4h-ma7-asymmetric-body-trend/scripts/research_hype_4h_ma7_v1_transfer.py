from __future__ import annotations

import argparse
from dataclasses import asdict, replace
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
FAMILY_DIR = ROOT / "research/hype/4h-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SOURCE_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ENGINE_PATH = SOURCE_DIR / "scripts/search_hype_1d_ma7_separated_trend.py"
ENGINE_SHA256 = (
    "c376f8bd1bae814b0ba53687380ee1060cf3cc3095ae815ebb0311ed1aef59e1"
)
BASE_PATH = SOURCE_DIR / "scripts/research_hype_1d_ma7_asymmetric_body_trend.py"
BASE_SHA256 = (
    "05d76943a671d1463f8950f1f6e317d8653831fd0f72ea825a039caa1fb2a386"
)
BAR_HOURS = 4
PHASES = (0, 2)
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Direct HYPE 1D MA7 V1 state-machine transfer to 4h bars."
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, expected_hash: str, name: str) -> Any:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_hash:
        raise RuntimeError(
            f"{path.name} drift: expected {expected_hash}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def frozen_configs(engine: Any) -> tuple[Any, Any]:
    long_config = engine.Config(
        side=1,
        entry_mode="reclaim",
        slope_lookback=1,
        slope_min_atr=0.02,
        confirm_days=1,
        entry_buffer_atr=0.0,
        pullback_lookback=5,
        pullback_touch_atr=0.0,
        breakout_lookback=2,
        exit_confirm_days=1,
        exit_buffer_atr=0.75,
        slope_exit_lookback=0,
        hard_stop_atr=0.0,
        trail_atr=1.5,
        max_hold_days=90,
        cooldown_days=2,
    )
    short_config = engine.Config(
        side=-1,
        entry_mode="reclaim",
        slope_lookback=2,
        slope_min_atr=0.02,
        confirm_days=1,
        entry_buffer_atr=0.1,
        pullback_lookback=10,
        pullback_touch_atr=0.0,
        breakout_lookback=5,
        exit_confirm_days=1,
        exit_buffer_atr=0.25,
        slope_exit_lookback=1,
        hard_stop_atr=1.5,
        trail_atr=4.0,
        max_hold_days=20,
        cooldown_days=5,
    )
    return long_config, short_config


def aggregate_4h(
    hourly: pd.DataFrame,
    *,
    phase_hours: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = hourly.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["bucket"] = (
        frame["ts"] - pd.Timedelta(hours=phase_hours)
    ).dt.floor("4h") + pd.Timedelta(hours=phase_hours)
    grouped = frame.groupby("bucket", sort=True)
    rows: list[dict[str, Any]] = []
    incomplete = 0
    for bucket, part in grouped:
        part = part.sort_values("ts")
        expected = pd.date_range(
            bucket,
            periods=BAR_HOURS,
            freq="1h",
            tz="UTC",
        )
        if len(part) != BAR_HOURS or not pd.DatetimeIndex(
            part["ts"]
        ).equals(expected):
            incomplete += 1
            continue
        rows.append(
            {
                "ts": pd.Timestamp(bucket),
                "open": float(part.iloc[0]["open"]),
                "high": float(part["high"].max()),
                "low": float(part["low"].min()),
                "close": float(part.iloc[-1]["close"]),
            }
        )
    bars = pd.DataFrame(rows)
    if bars.empty:
        raise RuntimeError(f"phase {phase_hours}: no complete 4h bars")
    hourly_index = frame.set_index("ts").sort_index()
    while len(bars):
        terminal_ts = pd.Timestamp(bars.iloc[-1]["ts"]) + pd.Timedelta(
            hours=BAR_HOURS
        )
        if terminal_ts in hourly_index.index:
            break
        bars = bars.iloc[:-1].copy()
    if bars.empty:
        raise RuntimeError(f"phase {phase_hours}: no terminal open")
    expected_bars = pd.date_range(
        bars.iloc[0]["ts"],
        bars.iloc[-1]["ts"],
        freq="4h",
        tz="UTC",
    )
    duplicate_ts = int(bars["ts"].duplicated().sum())
    missing_bars = len(expected_bars.difference(pd.DatetimeIndex(bars["ts"])))
    invalid_ohlc = int(
        (
            (bars["high"] < bars[["open", "close"]].max(axis=1))
            | (bars["low"] > bars[["open", "close"]].min(axis=1))
            | (bars["high"] < bars["low"])
            | (bars[["open", "high", "low", "close"]] <= 0.0).any(axis=1)
        ).sum()
    )
    blockers = duplicate_ts + missing_bars + invalid_ohlc
    if blockers:
        raise RuntimeError(
            f"phase {phase_hours}: 4h quality blockers={blockers}"
        )
    quality = {
        "aggregation": (
            f"UTC-aligned 4h bars with phase={phase_hours}h; "
            "exactly four explicit closed 1h bars"
        ),
        "rows": len(bars),
        "first_ts": pd.Timestamp(bars.iloc[0]["ts"]).isoformat(),
        "last_ts": pd.Timestamp(bars.iloc[-1]["ts"]).isoformat(),
        "terminal_open_ts": terminal_ts.isoformat(),
        "incomplete_edge_bins_dropped": incomplete,
        "duplicate_ts": duplicate_ts,
        "missing_bars": missing_bars,
        "invalid_ohlc_rows": invalid_ohlc,
        "blocker_count": blockers,
    }
    return bars, quality


def build_book(
    base: Any,
    hourly: pd.DataFrame,
    hourly_quality: dict[str, Any],
    funding_quality: dict[str, Any],
    *,
    phase_hours: int,
) -> Any:
    bars, quality = aggregate_4h(hourly, phase_hours=phase_hours)
    hourly_frame = hourly.copy()
    hourly_frame["ts"] = pd.to_datetime(hourly_frame["ts"], utc=True)
    hourly_frame = hourly_frame.set_index("ts").sort_index()
    terminal_ts = pd.Timestamp(quality["terminal_open_ts"])
    terminal_open = float(hourly_frame.loc[terminal_ts, "open"])
    zeros = np.zeros(len(bars), dtype="float64")
    return base.Book(
        ts=pd.DatetimeIndex(bars["ts"]),
        terminal_ts=terminal_ts,
        open=bars["open"].to_numpy("float64"),
        short_entry_open=zeros.copy(),
        post_short_entry_high=zeros.copy(),
        post_short_entry_low=zeros.copy(),
        high=bars["high"].to_numpy("float64"),
        low=bars["low"].to_numpy("float64"),
        close=bars["close"].to_numpy("float64"),
        funding_by_open=zeros.copy(),
        quality={
            "exchange": "Binance",
            "market": "USD-M perpetual",
            "symbol": "HYPEUSDT",
            "source_timeframe": "1h",
            "strategy_timeframe": "4h",
            "phase_hours": phase_hours,
            "hourly": hourly_quality,
            "bars": quality,
            "terminal_open": terminal_open,
        },
        funding_quality=funding_quality,
    )


def build_features(
    engine: Any,
    book: Any,
    hourly: pd.DataFrame,
    funding: pd.DataFrame,
) -> Any:
    close = pd.Series(book.close, dtype=float)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            pd.Series(book.high - book.low),
            pd.Series(book.high).sub(previous_close).abs(),
            pd.Series(book.low).sub(previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    hourly_frame = hourly.copy()
    hourly_frame["ts"] = pd.to_datetime(hourly_frame["ts"], utc=True)
    hourly_frame = hourly_frame.set_index("ts").sort_index()
    funding_frame = funding.copy()
    funding_frame["ts"] = pd.to_datetime(funding_frame["ts"], utc=True)
    funding_frame = funding_frame.sort_values("ts")
    hourly_open: list[np.ndarray] = []
    hourly_high: list[np.ndarray] = []
    hourly_low: list[np.ndarray] = []
    funding_events: list[list[Any]] = []
    for bar_start in book.ts:
        bar_end = pd.Timestamp(bar_start) + pd.Timedelta(hours=BAR_HOURS)
        rows = hourly_frame.loc[
            (hourly_frame.index >= bar_start)
            & (hourly_frame.index < bar_end)
        ]
        if len(rows) != BAR_HOURS:
            raise RuntimeError(
                f"expected four 1h bars from {bar_start}, got {len(rows)}"
            )
        hourly_open.append(rows["open"].to_numpy("float64"))
        hourly_high.append(rows["high"].to_numpy("float64"))
        hourly_low.append(rows["low"].to_numpy("float64"))
        events: list[Any] = []
        selected_funding = funding_frame.loc[
            funding_frame["ts"].ge(bar_start)
            & funding_frame["ts"].lt(bar_end)
        ]
        for row in selected_funding.itertuples(index=False):
            event_ts = pd.Timestamp(row.ts)
            event_hour = event_ts.floor("h")
            if event_hour not in rows.index:
                raise RuntimeError(f"funding event {event_ts} has no 1h bar")
            events.append(
                engine.FundingEvent(
                    ts=event_ts,
                    rate=float(row.funding_rate),
                    price=float(rows.loc[event_hour, "open"]),
                )
            )
        funding_events.append(events)
    windows = (2, 3, 5, 7, 10, 14)
    return engine.Features(
        ma7=close.rolling(7, min_periods=7).mean().to_numpy("float64"),
        atr7=true_range.rolling(7, min_periods=7)
        .mean()
        .to_numpy("float64"),
        prior_high={
            window: pd.Series(book.high)
            .rolling(window, min_periods=window)
            .max()
            .shift(1)
            .to_numpy("float64")
            for window in windows
        },
        prior_low={
            window: pd.Series(book.low)
            .rolling(window, min_periods=window)
            .min()
            .shift(1)
            .to_numpy("float64")
            for window in windows
        },
        hourly_open=np.asarray(hourly_open, dtype="float64"),
        hourly_high=np.asarray(hourly_high, dtype="float64"),
        hourly_low=np.asarray(hourly_low, dtype="float64"),
        funding_events=funding_events,
    )


def normalize_sharpe(result: Any) -> Any:
    path = pd.DataFrame(result.path)
    if path.empty:
        result.metrics["sharpe"] = math.nan
        return result
    equity = pd.Series(
        [1.0, *path["close_equity"].astype(float).tolist()],
        dtype=float,
    )
    returns = (
        equity.pct_change()
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    result.metrics["sharpe"] = (
        float(
            np.sqrt(365.25 * 24.0 / BAR_HOURS)
            * returns.mean()
            / returns.std(ddof=1)
        )
        if len(returns) >= 30 and returns.std(ddof=1) > 0.0
        else math.nan
    )
    return result


def run(
    engine: Any,
    book: Any,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
    *,
    start: int,
    end: int,
    slippage: float | None = None,
    signal_lag: int = 0,
) -> Any:
    kwargs: dict[str, Any] = {}
    if slippage is not None:
        kwargs["slippage"] = slippage
    result = engine.backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=start,
        terminal_index=end,
        retain=True,
        signal_lag=signal_lag,
        **kwargs,
    )
    return normalize_sharpe(result)


def audit_contract(
    engine: Any,
    contract: str,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any,
    *,
    prefit_end: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    windows = {
        "prefit": (0, prefit_end),
        "last_90d_flat": (prefit_end, book.count),
        "full": (0, book.count),
    }
    payload: dict[str, Any] = {"windows": {}}
    rows: list[dict[str, Any]] = []
    retained: dict[str, Any] = {}
    for window, (start, end) in windows.items():
        for variant, long_leg, short_leg in (
            ("combined", long_config, short_config),
            ("long_only", long_config, None),
            ("short_only", None, short_config),
        ):
            result = run(
                engine,
                book,
                features,
                long_leg,
                short_leg,
                start=start,
                end=end,
            )
            payload["windows"].setdefault(window, {})[variant] = (
                result.metrics
            )
            rows.append(
                {
                    "contract": contract,
                    "window": window,
                    "variant": variant,
                    **result.metrics,
                }
            )
            if window == "full":
                retained[variant] = result
    for variant, slippage, lag in (
        ("stress_8bps", engine.STRESS_SLIPPAGE, 0),
        ("one_bar_delay", None, 1),
    ):
        result = run(
            engine,
            book,
            features,
            long_config,
            short_config,
            start=0,
            end=book.count,
            slippage=slippage,
            signal_lag=lag,
        )
        payload[variant] = result.metrics
        rows.append(
            {
                "contract": contract,
                "window": "full",
                "variant": variant,
                **result.metrics,
            }
        )
    payload["_retained"] = retained
    return payload, rows


def phase_audit(
    engine: Any,
    contract: str,
    books: dict[int, Any],
    features: dict[int, Any],
    long_config: Any,
    short_config: Any,
) -> list[dict[str, Any]]:
    common_start = max(book.ts[0] for book in books.values())
    common_end = min(book.terminal_ts for book in books.values())
    rows: list[dict[str, Any]] = []
    for variant, long_leg, short_leg in (
        ("combined", long_config, short_config),
        ("long_only", long_config, None),
        ("short_only", None, short_config),
    ):
        for phase, book in sorted(books.items()):
            timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
            start = int(book.ts.searchsorted(common_start, side="left"))
            end = int(timestamps.searchsorted(common_end, side="right") - 1)
            result = run(
                engine,
                book,
                features[phase],
                long_leg,
                short_leg,
                start=start,
                end=end,
            )
            rows.append(
                {
                    "contract": contract,
                    "variant": variant,
                    "phase_hours": phase,
                    "common_start": common_start.isoformat(),
                    "common_end": common_end.isoformat(),
                    **result.metrics,
                }
            )
    return rows


def rolling_90d(
    engine: Any,
    contract: str,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    terminal = pd.DatetimeIndex([*book.ts, book.terminal_ts])
    window_bars = int(90 * 24 / BAR_HOURS)
    step_bars = int(30 * 24 / BAR_HOURS)
    start = 0
    while start + window_bars <= book.count:
        end = start + window_bars
        for variant, long_leg, short_leg in (
            ("combined", long_config, short_config),
            ("long_only", long_config, None),
            ("short_only", None, short_config),
        ):
            result = run(
                engine,
                book,
                features,
                long_leg,
                short_leg,
                start=start,
                end=end,
            )
            rows.append(
                {
                    "contract": contract,
                    "variant": variant,
                    "window_index": start // step_bars,
                    "window_start": terminal[start].isoformat(),
                    "window_end": terminal[end].isoformat(),
                    **result.metrics,
                }
            )
        start += step_bars
    return rows


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: clean_json(item)
            for key, item in value.items()
            if key != "_retained"
        }
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    engine = load_module(ENGINE_PATH, ENGINE_SHA256, "hype_4h_ma7_engine")
    base = load_module(BASE_PATH, BASE_SHA256, "hype_4h_ma7_base")
    long_config, short_config = frozen_configs(engine)
    clock_long = replace(
        long_config,
        max_hold_days=long_config.max_hold_days * 6,
        cooldown_days=long_config.cooldown_days * 6,
    )
    clock_short = replace(
        short_config,
        max_hold_days=short_config.max_hold_days * 6,
        cooldown_days=short_config.cooldown_days * 6,
    )
    if args.self_test:
        sample = pd.DataFrame(
            {
                "ts": pd.date_range(
                    "2026-01-01T00:00:00Z",
                    periods=9,
                    freq="1h",
                ),
                "open": np.arange(1.0, 10.0),
                "high": np.arange(1.5, 10.5),
                "low": np.arange(0.5, 9.5),
                "close": np.arange(1.25, 10.25),
            }
        )
        bars, quality = aggregate_4h(sample, phase_hours=0)
        assert len(bars) == 2
        assert quality["terminal_open_ts"] == "2026-01-01T08:00:00+00:00"
        assert clock_long.max_hold_days == 540
        assert clock_short.cooldown_days == 30
        print("self-test: PASS")
        return

    parent = base.load_parent()
    data_engine = parent.load_engine()
    hourly, hourly_quality = data_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = data_engine.load_and_audit_funding(ROOT)
    books = {
        phase: build_book(
            base,
            hourly,
            hourly_quality,
            funding_quality,
            phase_hours=phase,
        )
        for phase in PHASES
    }
    features = {
        phase: build_features(engine, book, hourly, funding)
        for phase, book in books.items()
    }
    book = books[0]
    prefit_end = int(book.ts.searchsorted(HOLDOUT_START, side="left"))
    if prefit_end <= 0 or prefit_end >= book.count:
        raise RuntimeError("invalid chronological split")
    contracts = {
        "bar_transfer": (long_config, short_config),
        "clock_equivalent": (clock_long, clock_short),
    }
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "HYPE-4H-MA7-Asymmetric-Body-Trend",
        "status": "explore / not promoted / not live-ready",
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V1",
        "source_engine": {
            "path": str(ENGINE_PATH.relative_to(ROOT)),
            "sha256": ENGINE_SHA256,
            "base_path": str(BASE_PATH.relative_to(ROOT)),
            "base_sha256": BASE_SHA256,
        },
        "contracts": {},
        "data_quality": {
            str(phase): books[phase].quality for phase in PHASES
        },
        "execution": (
            "closed 4h signal -> next 4h open; intrabar stops audited "
            "with constituent 1h bars; event-time funding"
        ),
    }
    metric_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    retained: dict[str, dict[str, Any]] = {}
    for contract, (long_leg, short_leg) in contracts.items():
        audit, rows = audit_contract(
            engine,
            contract,
            book,
            features[0],
            long_leg,
            short_leg,
            prefit_end=prefit_end,
        )
        retained[contract] = audit["_retained"]
        payload["contracts"][contract] = {
            "long_config": asdict(long_leg),
            "short_config": asdict(short_leg),
            **audit,
        }
        metric_rows.extend(rows)
        phase_rows.extend(
            phase_audit(
                engine,
                contract,
                books,
                features,
                long_leg,
                short_leg,
            )
        )
        rolling_rows.extend(
            rolling_90d(
                engine,
                contract,
                book,
                features[0],
                long_leg,
                short_leg,
            )
        )
        for variant, result in retained[contract].items():
            recent_rows.extend(
                {
                    "contract": contract,
                    "variant": variant,
                    **row,
                }
                for row in engine.recent_slices(result)
            )
            trade_rows.extend(
                {
                    "contract": contract,
                    "variant": variant,
                    **trade,
                }
                for trade in result.trades
            )
    payload["phase_audit"] = phase_rows
    payload["rolling_90d"] = {
        contract: {
            variant: {
                "count": len(selected),
                "positive": sum(
                    row["net_return_pct"] > 0.0 for row in selected
                ),
                "median_return_pct": float(
                    np.median([
                        row["net_return_pct"] for row in selected
                    ])
                ),
                "min_return_pct": min(
                    row["net_return_pct"] for row in selected
                ),
            }
            for variant in ("combined", "long_only", "short_only")
            for selected in [[
                row
                for row in rolling_rows
                if row["contract"] == contract
                and row["variant"] == variant
            ]]
        }
        for contract in contracts
    }
    payload["buy_and_hold"] = engine.buy_and_hold(book, features[0])
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "hype_4h_ma7_v1_transfer"
    clean_payload = clean_json(payload)
    (ARTIFACT_DIR / f"{stem}_summary_{args.run_date}.json").write_text(
        json.dumps(
            clean_payload,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(phase_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_phase_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv",
        index=False,
    )
    for contract in contracts:
        pd.DataFrame(retained[contract]["combined"].path).to_csv(
            ARTIFACT_DIR
            / f"{stem}_{contract}_path_{args.run_date}.csv",
            index=False,
        )
    print(
        json.dumps(
            {
                "contracts": {
                    contract: clean_payload["contracts"][contract]
                    for contract in contracts
                },
                "phase_audit": clean_payload["phase_audit"],
                "rolling_90d": clean_payload["rolling_90d"],
                "buy_and_hold": clean_payload["buy_and_hold"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
