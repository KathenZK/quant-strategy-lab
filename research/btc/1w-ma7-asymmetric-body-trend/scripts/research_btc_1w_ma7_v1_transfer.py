from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import UTC, datetime
import hashlib
import importlib.util
import inspect
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/1w-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
TRANSFER_PATH = (
    ROOT
    / "research/asset-portfolios/1d-ma7-separated-trend-transfer/scripts/"
    "research_binance_1d_ma7_separated_trend_transfer.py"
)
TRANSFER_SHA256 = (
    "d4b68183616c34af1eac5a583fdcf3fbec12778a48f7a4765731cb3750eb895a"
)
SYMBOL = "BTCUSDT"
SLUG = "btc_usdt_usdt"
WEEK_HOURS = 168
WEEK_DAYS = 7
PHASES = (0, 84)
RECENT_DAYS = {
    "1d": 1,
    "7d": 7,
    "1m": 30,
    "3m": 90,
    "6m": 182,
    "1y": 365,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Zero-tuning weekly MA7 transfer of HYPE daily V1 to BTCUSDT."
        )
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


def adapt_weekly_backtest(engine: Any) -> str:
    source = inspect.getsource(engine.backtest)
    needle = "ts + pd.Timedelta(days=1),"
    if source.count(needle) != 1:
        raise RuntimeError(
            "weekly engine adaptation expected one daily funding boundary"
        )
    adapted = source.replace(
        needle,
        "ts + pd.Timedelta(days=7),",
    )
    namespace: dict[str, Any] = {}
    exec(compile(adapted, "<weekly-backtest>", "exec"), engine.__dict__, namespace)
    engine.backtest = namespace["backtest"]
    return hashlib.sha256(adapted.encode("utf-8")).hexdigest()


def time_contracts(
    engine: Any,
    transfer: Any,
) -> dict[str, tuple[Any, Any]]:
    long_config, short_config = transfer.frozen_configs(engine)
    return {
        "bar_transfer": (long_config, short_config),
        "clock_equivalent": (
            replace(
                long_config,
                max_hold_days=13,
                cooldown_days=1,
            ),
            replace(
                short_config,
                max_hold_days=3,
                cooldown_days=1,
            ),
        ),
    }


def week_anchor(phase_hours: int) -> pd.Timestamp:
    return pd.Timestamp("1970-01-05T00:00:00Z") + pd.Timedelta(
        hours=phase_hours
    )


def aggregate_weekly(
    hourly: pd.DataFrame,
    *,
    phase_hours: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = hourly[["ts", "open", "high", "low", "close"]].copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    anchor = week_anchor(phase_hours)
    delta = frame["ts"] - anchor
    frame["week_number"] = (
        delta.dt.total_seconds() // (WEEK_HOURS * 3600)
    ).astype("int64")
    rows: list[dict[str, Any]] = []
    incomplete = 0
    for week_number, group in frame.groupby("week_number", sort=True):
        start = anchor + pd.Timedelta(
            hours=int(week_number) * WEEK_HOURS
        )
        expected = pd.date_range(start, periods=WEEK_HOURS, freq="1h")
        group = group.sort_values("ts")
        if len(group) != WEEK_HOURS or not pd.DatetimeIndex(
            group["ts"]
        ).equals(expected):
            incomplete += 1
            continue
        rows.append(
            {
                "ts": start,
                "open": float(group["open"].iloc[0]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group["close"].iloc[-1]),
            }
        )
    weekly = pd.DataFrame(rows)
    if weekly.empty:
        raise RuntimeError(f"phase {phase_hours}: no complete weekly bars")
    hourly_index = pd.DatetimeIndex(frame["ts"])
    while len(weekly) and (
        pd.Timestamp(weekly["ts"].iloc[-1]) + pd.Timedelta(days=7)
        not in hourly_index
    ):
        weekly = weekly.iloc[:-1].reset_index(drop=True)
        incomplete += 1
    if weekly.empty:
        raise RuntimeError(f"phase {phase_hours}: no terminal weekly open")
    gaps = weekly["ts"].diff().dropna()
    invalid = int(
        (
            (weekly[["open", "high", "low", "close"]] <= 0.0).any(axis=1)
            | weekly["high"].lt(
                weekly[["open", "close", "low"]].max(axis=1)
            )
            | weekly["low"].gt(
                weekly[["open", "close", "high"]].min(axis=1)
            )
        ).sum()
    )
    blockers = (
        int(weekly["ts"].duplicated().sum())
        + int(weekly.isna().any(axis=1).sum())
        + invalid
        + int((gaps != pd.Timedelta(days=7)).sum())
    )
    if blockers:
        raise RuntimeError(
            f"phase {phase_hours}: weekly aggregation blockers={blockers}"
        )
    quality = {
        "phase_hours": phase_hours,
        "anchor": anchor.isoformat(),
        "aggregation": "exactly 168 explicit closed hourly bars",
        "rows": len(weekly),
        "first_ts": weekly["ts"].iloc[0].isoformat(),
        "last_ts": weekly["ts"].iloc[-1].isoformat(),
        "incomplete_edge_bins_dropped": incomplete,
        "invalid_ohlc_rows": invalid,
        "blocker_count": blockers,
    }
    return weekly, quality


def build_weekly_book(
    transfer: Any,
    hourly: pd.DataFrame,
    source_quality: dict[str, Any],
    *,
    phase_hours: int,
) -> tuple[Any, dict[str, Any]]:
    weekly, weekly_quality = aggregate_weekly(
        hourly,
        phase_hours=phase_hours,
    )
    hourly_indexed = hourly.set_index("ts").sort_index()
    terminal_ts = pd.Timestamp(weekly["ts"].iloc[-1]) + pd.Timedelta(
        days=7
    )
    short_entry_open: list[float] = []
    post_high: list[float] = []
    post_low: list[float] = []
    for start in pd.DatetimeIndex(weekly["ts"]):
        entry_ts = start + pd.Timedelta(hours=1)
        end = start + pd.Timedelta(days=7)
        path = hourly_indexed.loc[
            (hourly_indexed.index >= entry_ts)
            & (hourly_indexed.index < end)
        ]
        if len(path) != WEEK_HOURS - 1:
            raise RuntimeError(
                f"phase {phase_hours}: expected 167 post-entry hours at {start}"
            )
        short_entry_open.append(float(path.loc[entry_ts, "open"]))
        post_high.append(float(path["high"].max()))
        post_low.append(float(path["low"].min()))
    quality = {
        **source_quality,
        "strategy_timeframe": "1w",
        "weekly": weekly_quality,
        "terminal_open_ts": terminal_ts.isoformat(),
        "terminal_open": float(hourly_indexed.loc[terminal_ts, "open"]),
        "short_entry_execution": (
            "observe weekly open trigger; execute at next 1h open"
        ),
    }
    book = transfer.Book(
        ts=pd.DatetimeIndex(weekly["ts"]),
        terminal_ts=terminal_ts,
        open=weekly["open"].to_numpy("float64"),
        short_entry_open=np.asarray(short_entry_open, dtype=float),
        post_short_entry_high=np.asarray(post_high, dtype=float),
        post_short_entry_low=np.asarray(post_low, dtype=float),
        high=weekly["high"].to_numpy("float64"),
        low=weekly["low"].to_numpy("float64"),
        close=weekly["close"].to_numpy("float64"),
        quality=quality,
        funding_quality=source_quality["funding"],
    )
    return book, weekly_quality


def build_weekly_features(
    engine: Any,
    book: Any,
    hourly: pd.DataFrame,
    funding: pd.DataFrame,
) -> Any:
    close = pd.Series(book.close, dtype=float)
    prior_close = close.shift(1)
    true_range = pd.concat(
        [
            pd.Series(book.high - book.low),
            pd.Series(np.abs(book.high - prior_close)),
            pd.Series(np.abs(book.low - prior_close)),
        ],
        axis=1,
    ).max(axis=1)
    hourly_indexed = hourly.set_index("ts").sort_index()
    funding_frame = funding.sort_values("ts").copy()
    hourly_open: list[np.ndarray] = []
    hourly_high: list[np.ndarray] = []
    hourly_low: list[np.ndarray] = []
    funding_events: list[list[Any]] = []
    for start in book.ts:
        end = pd.Timestamp(start) + pd.Timedelta(days=7)
        path = hourly_indexed.loc[
            (hourly_indexed.index >= start)
            & (hourly_indexed.index < end)
        ]
        if len(path) != WEEK_HOURS:
            raise RuntimeError(f"expected 168 hourly bars from {start}")
        hourly_open.append(path["open"].to_numpy("float64"))
        hourly_high.append(path["high"].to_numpy("float64"))
        hourly_low.append(path["low"].to_numpy("float64"))
        events: list[Any] = []
        selected = funding_frame.loc[
            funding_frame["ts"].ge(start)
            & funding_frame["ts"].lt(end)
        ]
        for row in selected.itertuples(index=False):
            event_ts = pd.Timestamp(row.ts)
            event_hour = event_ts.floor("h")
            if event_hour not in path.index:
                raise RuntimeError(
                    f"funding event {event_ts} has no hourly candle"
                )
            events.append(
                engine.FundingEvent(
                    ts=event_ts,
                    rate=float(row.funding_rate),
                    price=float(path.loc[event_hour, "open"]),
                )
            )
        funding_events.append(events)
    windows = (2, 5)
    return engine.Features(
        ma7=close.rolling(7, min_periods=7).mean().to_numpy("float64"),
        atr7=true_range.rolling(7, min_periods=7).mean().to_numpy("float64"),
        prior_high={
            window: pd.Series(book.high)
            .shift(1)
            .rolling(window, min_periods=window)
            .max()
            .to_numpy("float64")
            for window in windows
        },
        prior_low={
            window: pd.Series(book.low)
            .shift(1)
            .rolling(window, min_periods=window)
            .min()
            .to_numpy("float64")
            for window in windows
        },
        hourly_open=np.asarray(hourly_open, dtype=float),
        hourly_high=np.asarray(hourly_high, dtype=float),
        hourly_low=np.asarray(hourly_low, dtype=float),
        funding_events=funding_events,
    )


def normalize_weekly_result(result: Any) -> Any:
    equity = pd.Series(
        [1.0, *[float(row["close_equity"]) for row in result.path]],
        dtype=float,
    )
    returns = (
        equity.pct_change()
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    result.metrics["sharpe"] = (
        float(
            np.sqrt(365.25 / 7.0)
            * returns.mean()
            / returns.std(ddof=1)
        )
        if len(returns) >= 30 and returns.std(ddof=1) > 0.0
        else math.nan
    )
    days = float(result.metrics["days"])
    multiple = float(result.metrics["equity_multiple"])
    result.metrics["annualized_factor"] = (
        multiple ** (365.25 / days) if multiple > 0.0 else 0.0
    )
    positions = [int(row["position"]) for row in result.path[:-1]]
    result.metrics["exposure_pct"] = (
        100.0 * sum(position != 0 for position in positions) / len(positions)
        if positions
        else 0.0
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
    result = engine.backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=start,
        terminal_index=end,
        slippage=(
            slippage
            if slippage is not None
            else engine.BASE_SLIPPAGE
        ),
        signal_lag=signal_lag,
        retain=True,
    )
    return normalize_weekly_result(result)


def audit_window(
    engine: Any,
    transfer: Any,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any,
    *,
    start: int,
    end: int,
) -> dict[str, Any]:
    variants = {
        "combined": (long_config, short_config, None, 0),
        "combined_8bps": (
            long_config,
            short_config,
            engine.STRESS_SLIPPAGE,
            0,
        ),
        "combined_one_week_delay": (
            long_config,
            short_config,
            None,
            1,
        ),
        "long_only": (long_config, None, None, 0),
        "short_only": (None, short_config, None, 0),
    }
    output: dict[str, Any] = {"_results": {}}
    for label, (long_leg, short_leg, slippage, lag) in variants.items():
        result = run(
            engine,
            book,
            features,
            long_leg,
            short_leg,
            start=start,
            end=end,
            slippage=slippage,
            signal_lag=lag,
        )
        output[label] = result.metrics
        output["_results"][label] = result
    benchmark = engine.buy_and_hold(
        transfer._window_book(book, start, end),
        transfer._window_features(features, start, end),
    )
    output["buy_and_hold"] = benchmark
    output["excess_return_pct"] = (
        output["combined"]["net_return_pct"]
        - benchmark["net_return_pct"]
    )
    return output


def recent_rows(
    engine: Any,
    contract: str,
    variant: str,
    result: Any,
) -> list[dict[str, Any]]:
    span = (
        pd.Timestamp(result.metrics["end_ts"])
        - pd.Timestamp(result.metrics["start_ts"])
    ).total_seconds() / 86_400.0
    return [
        {
            "time_contract": contract,
            "variant": variant,
            **row,
        }
        for row in engine.recent_slices(result)
        if span >= RECENT_DAYS[row["window"]]
    ]


def rolling_rows(
    engine: Any,
    contract: str,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while start + 26 <= book.count:
        end = start + 26
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
                    "time_contract": contract,
                    "variant": variant,
                    "window_index": start // 13,
                    **result.metrics,
                }
            )
        start += 13
    return rows


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: clean_json(item)
            for key, item in value.items()
            if key != "_results"
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
    transfer = load_module(
        TRANSFER_PATH,
        TRANSFER_SHA256,
        "btc_1w_ma7_daily_transfer_helper",
    )
    engine = transfer.load_engine()
    adapted_engine_sha256 = adapt_weekly_backtest(engine)
    contracts = time_contracts(engine, transfer)
    if args.self_test:
        assert week_anchor(0).weekday() == 0
        assert week_anchor(84).weekday() == 3
        assert contracts["clock_equivalent"][0].max_hold_days == 13
        assert contracts["clock_equivalent"][1].max_hold_days == 3
        print("self-test: PASS")
        return

    hourly, funding, source_quality = transfer.load_and_audit(
        SYMBOL,
        SLUG,
    )
    source_quality = {
        **source_quality,
        "timeframe": "accepted 1h -> anchored 1w",
        "consumer_note": (
            "source helper's daily label replaced by this weekly contract"
        ),
    }
    books: dict[int, Any] = {}
    features: dict[int, Any] = {}
    weekly_quality: dict[int, dict[str, Any]] = {}
    for phase in PHASES:
        book, quality = build_weekly_book(
            transfer,
            hourly,
            source_quality,
            phase_hours=phase,
        )
        books[phase] = book
        features[phase] = build_weekly_features(
            engine,
            book,
            hourly,
            funding,
        )
        weekly_quality[phase] = quality

    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "BTC-1W-MA7-Asymmetric-Body-Trend",
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V1",
        "status": "explore / not promoted / not live-ready",
        "engine": {
            "source_path": str(transfer.ENGINE_PATH.relative_to(ROOT)),
            "source_sha256": transfer.ENGINE_SHA256,
            "weekly_adapted_source_sha256": adapted_engine_sha256,
            "adaptation": (
                "only no-stop funding boundary changed from 1d to 7d; "
                "weekly Sharpe recomputed with sqrt(365.25/7)"
            ),
        },
        "data_quality": {
            "source": source_quality,
            "weekly": {
                str(phase): quality
                for phase, quality in weekly_quality.items()
            },
        },
        "contracts": {
            name: {
                "long_config": asdict(long_config),
                "short_config": asdict(short_config),
            }
            for name, (long_config, short_config) in contracts.items()
        },
        "primary_phase_hours": 0,
        "phase_audit_hours": 84,
        "results": {},
        "phase_audit": [],
        "rolling_26w": {},
    }
    metric_rows: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    rolling: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []

    for contract, (long_config, short_config) in contracts.items():
        audit = audit_window(
            engine,
            transfer,
            books[0],
            features[0],
            long_config,
            short_config,
            start=0,
            end=books[0].count,
        )
        payload["results"][contract] = audit
        for variant, metrics in audit.items():
            if variant != "_results" and isinstance(metrics, dict):
                metric_rows.append(
                    {
                        "time_contract": contract,
                        "phase_hours": 0,
                        "variant": variant,
                        **metrics,
                    }
                )
        for variant in ("combined", "long_only", "short_only"):
            result = audit["_results"][variant]
            recent.extend(
                recent_rows(engine, contract, variant, result)
            )
            trades.extend(
                {
                    "time_contract": contract,
                    "variant": variant,
                    **trade,
                }
                for trade in result.trades
            )

        for phase in PHASES:
            phase_audit = audit_window(
                engine,
                transfer,
                books[phase],
                features[phase],
                long_config,
                short_config,
                start=0,
                end=books[phase].count,
            )
            for variant in ("combined", "long_only", "short_only"):
                row = {
                    "time_contract": contract,
                    "phase_hours": phase,
                    "variant": variant,
                    **phase_audit[variant],
                }
                phase_rows.append(row)
        contract_rolling = rolling_rows(
            engine,
            contract,
            books[0],
            features[0],
            long_config,
            short_config,
        )
        rolling.extend(contract_rolling)
        payload["rolling_26w"][contract] = {
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
                for row in contract_rolling
                if row["variant"] == variant
            ]]
            if selected
        }
    payload["phase_audit"] = phase_rows

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "btc_1w_ma7_v1_transfer"
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
    pd.DataFrame(recent).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(phase_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_phase_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_26w_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(trades).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv",
        index=False,
    )
    for contract in contracts:
        result = payload["results"][contract]["_results"]["combined"]
        pd.DataFrame(result.path).to_csv(
            ARTIFACT_DIR
            / f"{stem}_{contract}_path_{args.run_date}.csv",
            index=False,
        )
    print(
        json.dumps(
            {
                "results": clean_payload["results"],
                "phase_audit": clean_payload["phase_audit"],
                "rolling_26w": clean_payload["rolling_26w"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
