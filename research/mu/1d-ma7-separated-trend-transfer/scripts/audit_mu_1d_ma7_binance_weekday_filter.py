from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterator

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/mu/1d-ma7-separated-trend-transfer"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
TRANSFER_PATH = (
    FAMILY_DIR
    / "scripts/research_mu_1d_ma7_dual_market_transfer.py"
)
TRANSFER_SHA256 = (
    "c2990a8fc0dd5cab13cc65269e9dd8629133c3885c2a2f12b42764e409ff2c57"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit MUUSDT daily MA7 after excluding weekend decisions."
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


def weekday_book(sox: Any, book: Any) -> Any:
    weekday_indices = np.flatnonzero(np.asarray(book.ts.weekday < 5))
    terminal_ts = pd.Timestamp(book.terminal_ts)
    if terminal_ts.weekday() < 5:
        terminal_open = float(book.quality["terminal_open"])
        strategy_indices = weekday_indices
    else:
        if len(weekday_indices) < 2:
            raise RuntimeError("insufficient weekday bars for a terminal open")
        terminal_index = int(weekday_indices[-1])
        terminal_ts = pd.Timestamp(book.ts[terminal_index])
        terminal_open = float(book.open[terminal_index])
        strategy_indices = weekday_indices[:-1]
    if not len(strategy_indices):
        raise RuntimeError("no weekday bars")
    quality = {
        **book.quality,
        "weekend_contract": "literal_drop",
        "dropped_weekend_daily_bars": int(
            book.count - len(strategy_indices)
        ),
        "terminal_open": terminal_open,
    }
    return sox.Book(
        ts=book.ts[strategy_indices],
        terminal_ts=terminal_ts,
        open=book.open[strategy_indices],
        short_entry_open=book.short_entry_open[strategy_indices],
        post_short_entry_high=book.post_short_entry_high[strategy_indices],
        post_short_entry_low=book.post_short_entry_low[strategy_indices],
        high=book.high[strategy_indices],
        low=book.low[strategy_indices],
        close=book.close[strategy_indices],
        quality=quality,
    )


def mapped_weekday_features(
    full_book: Any,
    full_features: Any,
    signal_book: Any,
    signal_features: Any,
) -> Any:
    compact_ts = pd.DatetimeIndex(signal_book.ts)
    mapped = compact_ts.searchsorted(full_book.ts, side="right") - 1

    def expand(values: np.ndarray) -> np.ndarray:
        output = np.full(full_book.count, np.nan, dtype=float)
        valid = mapped >= 0
        output[valid] = np.asarray(values, dtype=float)[mapped[valid]]
        return output

    feature_type = type(full_features)
    return feature_type(
        ma7=expand(signal_features.ma7),
        atr7=expand(signal_features.atr7),
        prior_high={
            key: expand(values)
            for key, values in signal_features.prior_high.items()
        },
        prior_low={
            key: expand(values)
            for key, values in signal_features.prior_low.items()
        },
        hourly_open=full_features.hourly_open,
        hourly_high=full_features.hourly_high,
        hourly_low=full_features.hourly_low,
        funding_events=full_features.funding_events,
    )


@contextmanager
def weekday_decision_gate(
    engine: Any,
    full_book: Any,
    signal_book: Any,
    signal_features: Any,
) -> Iterator[None]:
    original_close_entry = engine.close_entry_signal
    original_open_entry = engine.open_entry_signal
    original_exit = engine.signal_exit
    compact_ts = pd.DatetimeIndex(signal_book.ts)

    def execution_index(decision_index: int) -> int | None:
        current = decision_index + 1
        if current < 0 or current >= full_book.count:
            return None
        if pd.Timestamp(full_book.ts[current]).weekday() >= 5:
            return None
        return current

    def prior_weekday_index(current: int) -> int:
        execution_ts = pd.Timestamp(full_book.ts[current])
        return int(compact_ts.searchsorted(execution_ts, side="left") - 1)

    def gated_close_entry(
        config: Any,
        _book: Any,
        _features: Any,
        decision_index: int,
    ) -> bool:
        current = execution_index(decision_index)
        if current is None:
            return False
        compact_index = prior_weekday_index(current)
        return (
            compact_index >= 0
            and original_close_entry(
                config,
                signal_book,
                signal_features,
                compact_index,
            )
        )

    def gated_exit(
        config: Any,
        _book: Any,
        _features: Any,
        decision_index: int,
        bars_held: int,
    ) -> str:
        current = execution_index(decision_index)
        if current is None:
            return ""
        compact_index = prior_weekday_index(current)
        if compact_index < 0:
            return ""
        return original_exit(
            config,
            signal_book,
            signal_features,
            compact_index,
            bars_held,
        )

    def gated_open_entry(
        config: Any,
        _book: Any,
        _features: Any,
        current_index: int,
    ) -> bool:
        if current_index < 0 or current_index >= full_book.count:
            return False
        execution_ts = pd.Timestamp(full_book.ts[current_index])
        if execution_ts.weekday() >= 5:
            return False
        compact_index = int(
            compact_ts.searchsorted(execution_ts, side="left")
        )
        if (
            compact_index >= signal_book.count
            or compact_ts[compact_index] != execution_ts
        ):
            return False
        return original_open_entry(
            config,
            signal_book,
            signal_features,
            compact_index,
        )

    engine.close_entry_signal = gated_close_entry
    engine.open_entry_signal = gated_open_entry
    engine.signal_exit = gated_exit
    try:
        yield
    finally:
        engine.close_entry_signal = original_close_entry
        engine.open_entry_signal = original_open_entry
        engine.signal_exit = original_exit


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
) -> Any:
    kwargs: dict[str, Any] = {}
    if slippage is not None:
        kwargs["slippage"] = slippage
    return engine.backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=start,
        terminal_index=end,
        retain=True,
        **kwargs,
    )


def window_indices(
    book: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> tuple[int, int]:
    timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
    start = int(book.ts.searchsorted(start_ts, side="left"))
    end = min(
        book.count,
        int(timestamps.searchsorted(end_ts, side="left")),
    )
    if end <= start:
        raise RuntimeError(f"empty window {start_ts} -> {end_ts}")
    return start, end


def audit_mode(
    engine: Any,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any,
    *,
    start: int,
    end: int,
    gate: Any | None = None,
) -> dict[str, Any]:
    rows: dict[str, Any] = {"_results": {}}
    variants = {
        "combined": (long_config, short_config, None),
        "combined_8bps": (
            long_config,
            short_config,
            engine.STRESS_SLIPPAGE,
        ),
        "long_only": (long_config, None, None),
        "short_only": (None, short_config, None),
    }
    context = gate if gate is not None else _null_context()
    with context:
        for label, (long_leg, short_leg, slippage) in variants.items():
            result = run(
                engine,
                book,
                features,
                long_leg,
                short_leg,
                start=start,
                end=end,
                slippage=slippage,
            )
            rows[label] = result.metrics
            rows["_results"][label] = result
    return rows


@contextmanager
def _null_context() -> Iterator[None]:
    yield


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
        "mu_1d_ma7_weekday_transfer",
    )
    hype_helper = transfer.load_module(
        transfer.HYPE_HELPER_PATH,
        transfer.HYPE_HELPER_SHA256,
        "mu_1d_ma7_weekday_hype_helper",
    )
    mu_audit = transfer.load_module(
        transfer.MU_AUDIT_PATH,
        transfer.MU_AUDIT_SHA256,
        "mu_1d_ma7_weekday_data_audit",
    )
    sox = transfer.load_module(
        transfer.SOX_HELPER_PATH,
        transfer.SOX_HELPER_SHA256,
        "mu_1d_ma7_weekday_sox_helper",
    )
    engine = hype_helper.load_module(
        hype_helper.ENGINE_PATH,
        hype_helper.ENGINE_SHA256,
        "mu_1d_ma7_weekday_engine",
    )
    base = hype_helper.load_module(
        hype_helper.BASE_PATH,
        hype_helper.BASE_SHA256,
        "mu_1d_ma7_weekday_base",
    )
    long_config, short_config = hype_helper.frozen_configs(engine)
    if args.self_test:
        sample = sox.Book(
            ts=pd.date_range(
                "2026-04-10T00:00:00Z",
                periods=4,
                freq="1D",
            ),
            terminal_ts=pd.Timestamp("2026-04-14T00:00:00Z"),
            open=np.ones(4),
            short_entry_open=np.ones(4),
            post_short_entry_high=np.ones(4),
            post_short_entry_low=np.ones(4),
            high=np.ones(4),
            low=np.ones(4),
            close=np.ones(4),
            quality={"terminal_open": 1.0},
        )
        filtered = weekday_book(sox, sample)
        assert list(filtered.ts.weekday) == [4, 0]
        assert filtered.quality["dropped_weekend_daily_bars"] == 2
        print("self-test: PASS")
        return

    bars_15m, data_quality, funding, funding_quality = (
        transfer.load_binance_data(mu_audit)
    )
    hourly, hourly_quality = transfer.aggregate_hourly(bars_15m)
    parent = base.load_parent()
    full_books: dict[int, Any] = {}
    full_features: dict[int, Any] = {}
    weekday_books: dict[int, Any] = {}
    weekday_features: dict[int, Any] = {}
    executable_features: dict[int, Any] = {}
    for phase in (0, 12):
        book = base.build_book(
            parent,
            hourly,
            {
                **hourly_quality,
                "source_dataset_quality": data_quality,
            },
            funding,
            funding_quality,
            phase_hours=phase,
        )
        book.quality.update(
            {
                "exchange": "Binance",
                "market": "USD-M TRADIFI_PERPETUAL",
                "symbol": "MUUSDT",
            }
        )
        features = engine.build_features(book, hourly, funding)
        compact_book = weekday_book(sox, book)
        compact_features = engine.build_features(
            compact_book,
            hourly,
            funding,
        )
        full_books[phase] = book
        full_features[phase] = features
        weekday_books[phase] = compact_book
        weekday_features[phase] = compact_features
        executable_features[phase] = mapped_weekday_features(
            book,
            features,
            compact_book,
            compact_features,
        )

    nasdaq_overlap_end = pd.Timestamp("2026-06-16T00:00:00Z")
    windows = {
        "full_available": (
            full_books[0].ts[0],
            full_books[0].terminal_ts,
        ),
        "nasdaq_common_overlap": (
            full_books[0].ts[0],
            nasdaq_overlap_end,
        ),
    }
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "MU-1D-MA7-Separated-Trend-Transfer",
        "source_version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V1",
        "status": "explore / not promoted / not live-ready",
        "contracts": {
            "baseline_7d": (
                "all UTC daily bars; signals, stops and funding active daily"
            ),
            "literal_weekday_only": (
                "drop Saturday/Sunday bars, signals, stop paths and funding; "
                "counterfactual and not live-executable on 24/7 MUUSDT"
            ),
            "weekday_signal_executable": (
                "SMA7/ATR7 and discretionary signals use weekday bars only; "
                "Saturday/Sunday entries and signal exits disabled; existing "
                "positions retain weekend price path, protective stops, "
                "trailing risk management and funding"
            ),
        },
        "caveats": [
            "Executable-gate cooldown and max-hold clocks remain calendar-day clocks.",
            "Phase uses the weekday of each shifted daily bucket's UTC opening timestamp.",
        ],
        "windows": {},
        "phase_audit": [],
    }
    metric_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []

    for window_name, (start_ts, end_ts) in windows.items():
        output: dict[str, Any] = {}
        base_start, base_end = window_indices(
            full_books[0],
            start_ts,
            end_ts,
        )
        output["baseline_7d"] = audit_mode(
            engine,
            full_books[0],
            full_features[0],
            long_config,
            short_config,
            start=base_start,
            end=base_end,
        )
        literal_start, literal_end = window_indices(
            weekday_books[0],
            start_ts,
            end_ts,
        )
        output["literal_weekday_only"] = audit_mode(
            engine,
            weekday_books[0],
            weekday_features[0],
            long_config,
            short_config,
            start=literal_start,
            end=literal_end,
        )
        output["weekday_signal_executable"] = audit_mode(
            engine,
            full_books[0],
            executable_features[0],
            long_config,
            short_config,
            start=base_start,
            end=base_end,
            gate=weekday_decision_gate(
                engine,
                full_books[0],
                weekday_books[0],
                weekday_features[0],
            ),
        )
        payload["windows"][window_name] = output
        for mode, audit in output.items():
            for variant, metrics in audit.items():
                if variant == "_results":
                    continue
                metric_rows.append(
                    {
                        "window": window_name,
                        "mode": mode,
                        "variant": variant,
                        **metrics,
                    }
                )
            if window_name == "full_available":
                for variant, result in audit["_results"].items():
                    trade_rows.extend(
                        {
                            "mode": mode,
                            "variant": variant,
                            **trade,
                        }
                        for trade in result.trades
                    )

    for phase in (0, 12):
        for mode in (
            "baseline_7d",
            "literal_weekday_only",
            "weekday_signal_executable",
        ):
            book = (
                weekday_books[phase]
                if mode == "literal_weekday_only"
                else full_books[phase]
            )
            features = (
                weekday_features[phase]
                if mode == "literal_weekday_only"
                else (
                    executable_features[phase]
                    if mode == "weekday_signal_executable"
                    else full_features[phase]
                )
            )
            start, end = 0, book.count
            gate = (
                weekday_decision_gate(
                    engine,
                    full_books[phase],
                    weekday_books[phase],
                    weekday_features[phase],
                )
                if mode == "weekday_signal_executable"
                else None
            )
            audit = audit_mode(
                engine,
                book,
                features,
                long_config,
                short_config,
                start=start,
                end=end,
                gate=gate,
            )
            for variant in ("combined", "long_only", "short_only"):
                payload["phase_audit"].append(
                    {
                        "mode": mode,
                        "phase_hours": phase,
                        "variant": variant,
                        **audit[variant],
                    }
                )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "mu_1d_ma7_binance_weekday_filter"
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
    pd.DataFrame(payload["phase_audit"]).to_csv(
        ARTIFACT_DIR / f"{stem}_phase_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv",
        index=False,
    )
    print(
        json.dumps(
            {
                "windows": clean_payload["windows"],
                "phase_audit": clean_payload["phase_audit"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
