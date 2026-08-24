from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
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
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-specific-search"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
HYPE_FAMILY = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"

ENGINE_PATH = HYPE_FAMILY / "scripts/search_hype_1d_ma7_separated_trend.py"
ENGINE_SHA256 = "c376f8bd1bae814b0ba53687380ee1060cf3cc3095ae815ebb0311ed1aef59e1"
HYPE_BASE_PATH = HYPE_FAMILY / "scripts/research_hype_1d_ma7_asymmetric_body_trend.py"
HYPE_BASE_SHA256 = "05d76943a671d1463f8950f1f6e317d8653831fd0f72ea825a039caa1fb2a386"
TRANSFER_PATH = (
    ROOT
    / "research/asset-portfolios/1d-ma7-separated-trend-transfer/scripts"
    / "research_binance_1d_ma7_separated_trend_transfer.py"
)
TRANSFER_SHA256 = "d4b68183616c34af1eac5a583fdcf3fbec12778a48f7a4765731cb3750eb895a"
HYPE_SUMMARY = HYPE_FAMILY / "artifacts/hype_1d_ma7_separated_summary_2026-08-04.json"
HYPE_SUMMARY_SHA256 = "ba6245f5ca1811cac9566abc78b09fdf24e846fd70a0f9265aaa8dd9360c97ae"
SHARED_SUMMARY = (
    ARTIFACT_DIR
    / "binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json"
)
SHARED_SUMMARY_SHA256 = "ecaf0d65ddc7ed114acd078656e7da948a6ed5399c1b6292d716fb91199031be"

HISTORICAL_HOUR_CUTOFF = pd.Timestamp("2026-07-30T04:00:00Z")
HYPE_SPLIT = pd.Timestamp("2026-05-01T00:00:00Z")
SHARED_SPLIT = pd.Timestamp("2026-02-01T00:00:00Z")
PHASES = (0, 12)
ASSETS = {"BTCUSDT": "btc_usdt_usdt", "ETHUSDT": "eth_usdt_usdt"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit MA7 long-exit-to-short reversal on HYPE/BTC/ETH."
    )
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_pinned(path: Path, digest: str, name: str) -> Any:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        raise RuntimeError(f"{path.name} drift: expected {digest}, got {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_pinned_json(path: Path, digest: str) -> dict[str, Any]:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        raise RuntimeError(f"{path.name} drift: expected {digest}, got {actual}")
    return json.loads(path.read_text(encoding="utf-8"))


class LongConfigProxy:
    """Forward a frozen config while allowing exit-specific cooldown."""

    def __init__(self, base: Any) -> None:
        self.base = base
        self.active_cooldown = int(base.cooldown_days)

    @property
    def cooldown_days(self) -> int:
        return self.active_cooldown

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base, name)


@contextmanager
def reversal_hooks(
    engine: Any,
    long_proxy: LongConfigProxy,
) -> Iterator[None]:
    """Force short entry only immediately after a long hysteresis exit."""

    original_exit = engine.signal_exit
    original_close_entry = engine.close_entry_signal
    pending: dict[str, int | None] = {"index": None}

    def wrapped_exit(
        config: Any,
        book: Any,
        features: Any,
        index: int,
        bars_held: int,
    ) -> str:
        reason = original_exit(config, book, features, index, bars_held)
        if int(config.side) > 0 and reason:
            is_reversal = reason == "ma7_hysteresis_exit"
            long_proxy.active_cooldown = (
                0 if is_reversal else int(long_proxy.base.cooldown_days)
            )
            pending["index"] = index if is_reversal else None
        return reason

    def wrapped_close_entry(
        config: Any,
        book: Any,
        features: Any,
        index: int,
    ) -> bool:
        if int(config.side) > 0:
            signal = original_close_entry(config, book, features, index)
            if signal:
                long_proxy.active_cooldown = int(long_proxy.base.cooldown_days)
            return signal
        if pending["index"] == index:
            pending["index"] = None
            return True
        if pending["index"] is not None and pending["index"] != index:
            pending["index"] = None
        return original_close_entry(config, book, features, index)

    engine.signal_exit = wrapped_exit
    engine.close_entry_signal = wrapped_close_entry
    try:
        yield
    finally:
        engine.signal_exit = original_exit
        engine.close_entry_signal = original_close_entry


def run_strategy(
    engine: Any,
    book: Any,
    features: Any,
    long_config: Any,
    short_config: Any,
    *,
    variant: str,
    start: int,
    end: int,
    slippage: float,
    signal_lag: int = 0,
    retain: bool = False,
) -> Any:
    kwargs = {
        "long_config": long_config,
        "short_config": short_config,
        "start_index": start,
        "terminal_index": end,
        "slippage": slippage,
        "signal_lag": signal_lag,
        "retain": retain,
    }
    if variant == "R0_baseline":
        return engine.backtest(book, features, **kwargs)
    if variant != "R1_long_exit_short_reversal":
        raise ValueError(variant)
    proxy = LongConfigProxy(long_config)
    kwargs["long_config"] = proxy
    with reversal_hooks(engine, proxy):
        return engine.backtest(book, features, **kwargs)


def annotate_trades(
    result: Any,
    variant: str,
    *,
    engine: Any,
    book: Any,
    features: Any,
    short_config: Any,
    signal_lag: int = 0,
) -> pd.DataFrame:
    frame = pd.DataFrame(result.trades)
    if frame.empty:
        return frame
    frame["entry_source"] = "original_entry"
    if variant == "R1_long_exit_short_reversal":
        for index in range(1, len(frame)):
            previous = frame.iloc[index - 1]
            current = frame.iloc[index]
            if (
                current["side"] == "short"
                and previous["side"] == "long"
                and previous["exit_reason"] == "ma7_hysteresis_exit"
                and current["entry_ts"] == previous["exit_ts"]
            ):
                entry_ts = pd.Timestamp(current["entry_ts"])
                entry_index = int(
                    pd.DatetimeIndex([*book.ts, book.terminal_ts]).searchsorted(
                        entry_ts
                    )
                )
                decision_index = entry_index - 1 - signal_lag
                natural_close = engine.close_entry_signal(
                    short_config, book, features, decision_index
                )
                natural_open = engine.open_entry_signal(
                    short_config, book, features, entry_index - signal_lag
                )
                frame.loc[index, "entry_source"] = (
                    "natural_same_open"
                    if natural_close or natural_open
                    else "forced_long_exit_reversal"
                )
    return frame


def trade_attribution(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "long_trades": 0,
            "short_trades": 0,
            "short_net_pnl": 0.0,
            "short_profit_factor": math.nan,
            "forced_reversal_trades": 0,
            "forced_reversal_net_pnl": 0.0,
            "forced_reversal_win_rate": math.nan,
        }
    short = frame.loc[frame["side"].eq("short")]
    forced = frame.loc[frame["entry_source"].eq("forced_long_exit_reversal")]
    short_wins = short.loc[short["net_pnl"] > 0.0, "net_pnl"].sum()
    short_losses = -short.loc[short["net_pnl"] < 0.0, "net_pnl"].sum()
    return {
        "long_trades": int(frame["side"].eq("long").sum()),
        "short_trades": int(len(short)),
        "short_net_pnl": float(short["net_pnl"].sum()),
        "short_profit_factor": (
            float(short_wins / short_losses)
            if short_losses > 0.0
            else (math.inf if short_wins > 0.0 else math.nan)
        ),
        "forced_reversal_trades": int(len(forced)),
        "forced_reversal_net_pnl": float(forced["net_pnl"].sum()),
        "forced_reversal_win_rate": (
            float((forced["net_pnl"] > 0.0).mean()) if len(forced) else math.nan
        ),
    }


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def window_index(book: Any, timestamp: pd.Timestamp) -> int:
    return int(pd.DatetimeIndex(book.ts).searchsorted(timestamp))


def main() -> None:
    args = parse_args()
    engine = load_pinned(ENGINE_PATH, ENGINE_SHA256, "ma7_reversal_engine")
    hype_base = load_pinned(HYPE_BASE_PATH, HYPE_BASE_SHA256, "ma7_reversal_hype_base")
    transfer = load_pinned(TRANSFER_PATH, TRANSFER_SHA256, "ma7_reversal_transfer")
    hype_summary = read_pinned_json(HYPE_SUMMARY, HYPE_SUMMARY_SHA256)
    shared_summary = read_pinned_json(SHARED_SUMMARY, SHARED_SUMMARY_SHA256)

    hype_selected = hype_summary["historically_profitable_all_checks"][0]
    hype_configs = (
        engine.Config(**hype_selected["long_config"]),
        engine.Config(**hype_selected["short_config"]),
    )
    shared_selected = shared_summary["selections"]["BTC_ETH_shared"]
    shared_configs = (
        engine.Config(**shared_selected["long_config"]),
        engine.Config(**shared_selected["short_config"]),
    )

    parent = hype_base.load_parent()
    market_engine = parent.load_engine()
    hype_hourly, hype_quality = market_engine.audit_and_load_market(ROOT, "1h")
    hype_funding, hype_funding_quality = market_engine.load_and_audit_funding(ROOT)
    hype_hourly["ts"] = pd.to_datetime(hype_hourly["ts"], utc=True)
    hype_funding["ts"] = pd.to_datetime(hype_funding["ts"], utc=True)
    hype_historical_hourly = hype_hourly.loc[
        hype_hourly["ts"] <= HISTORICAL_HOUR_CUTOFF
    ].copy()
    hype_historical_funding = hype_funding.loc[
        hype_funding["ts"] <= HISTORICAL_HOUR_CUTOFF
    ].copy()

    route_books: dict[str, dict[int, Any]] = {"HYPE_V1": {}}
    route_features: dict[str, dict[int, Any]] = {"HYPE_V1": {}}
    route_configs = {"HYPE_V1": hype_configs}
    route_splits = {"HYPE_V1": HYPE_SPLIT}
    data_quality: dict[str, Any] = {"HYPE_V1": hype_quality}

    for phase in PHASES:
        book = hype_base.build_book(
            parent,
            hype_historical_hourly,
            hype_quality,
            hype_historical_funding,
            hype_funding_quality,
            phase_hours=phase,
        )
        route_books["HYPE_V1"][phase] = book
        route_features["HYPE_V1"][phase] = engine.build_features(
            book, hype_historical_hourly, hype_historical_funding
        )

    for symbol, slug in ASSETS.items():
        hourly, funding, quality = transfer.load_and_audit(symbol, slug)
        route_books[symbol] = {}
        route_features[symbol] = {}
        route_configs[symbol] = shared_configs
        route_splits[symbol] = SHARED_SPLIT
        data_quality[symbol] = quality
        for phase in PHASES:
            book = transfer.build_book(symbol, hourly, quality, phase_hours=phase)
            route_books[symbol][phase] = book
            route_features[symbol][phase] = engine.build_features(
                book, hourly, funding
            )

    # Invariant: unchanged baseline still reproduces the registered HYPE evidence.
    anchor = run_strategy(
        engine,
        route_books["HYPE_V1"][0],
        route_features["HYPE_V1"][0],
        *hype_configs,
        variant="R0_baseline",
        start=0,
        end=route_books["HYPE_V1"][0].count,
        slippage=engine.BASE_SLIPPAGE,
    )
    expected_equity = float(
        hype_selected["windows"]["full"]["base"]["equity_multiple"]
    )
    if not math.isclose(
        anchor.metrics["equity_multiple"],
        expected_equity,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError(
            "HYPE baseline anchor drift: "
            f"{anchor.metrics['equity_multiple']} vs {expected_equity}"
        )
    if args.self_test:
        probe = run_strategy(
            engine,
            route_books["HYPE_V1"][0],
            route_features["HYPE_V1"][0],
            *hype_configs,
            variant="R1_long_exit_short_reversal",
            start=0,
            end=route_books["HYPE_V1"][0].count,
            slippage=engine.BASE_SLIPPAGE,
            retain=True,
        )
        probe_trades = annotate_trades(
            probe,
            "R1_long_exit_short_reversal",
            engine=engine,
            book=route_books["HYPE_V1"][0],
            features=route_features["HYPE_V1"][0],
            short_config=hype_configs[1],
        )
        forced = probe_trades.loc[
            probe_trades["entry_source"].eq("forced_long_exit_reversal")
        ]
        if forced.empty:
            raise AssertionError("self-test expected at least one forced reversal")
        if engine.signal_exit.__name__ != "signal_exit":
            raise AssertionError("engine hooks were not restored")
        print(
            "self-test passed: baseline anchor exact; "
            f"forced reversals={len(forced)}; hooks restored"
        )
        return

    variants = ("R0_baseline", "R1_long_exit_short_reversal")
    metric_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    primary: dict[str, dict[str, Any]] = {}

    for route, phase_books in route_books.items():
        long_config, short_config = route_configs[route]
        book = phase_books[0]
        features = route_features[route][0]
        split = window_index(book, route_splits[route])
        windows = {
            "development_or_prefit": (0, split),
            "researcher_exposed_holdout": (split, book.count),
            "full": (0, book.count),
        }
        primary[route] = {}
        for variant in variants:
            primary[route][variant] = {}
            for window, (start, end) in windows.items():
                result = run_strategy(
                    engine,
                    book,
                    features,
                    long_config,
                    short_config,
                    variant=variant,
                    start=start,
                    end=end,
                    slippage=engine.BASE_SLIPPAGE,
                    retain=window == "full",
                )
                trades = annotate_trades(
                    result,
                    variant,
                    engine=engine,
                    book=book,
                    features=features,
                    short_config=short_config,
                )
                attribution = trade_attribution(trades)
                metric_rows.append(
                    {
                        "route": route,
                        "variant": variant,
                        "window": window,
                        "execution": "base_4bps",
                        **result.metrics,
                        **attribution,
                    }
                )
                if window == "full":
                    primary[route][variant] = {
                        "metrics": result.metrics,
                        "attribution": attribution,
                    }
                    for row in engine.recent_slices(result):
                        recent_rows.append(
                            {"route": route, "variant": variant, **row}
                        )
                    for row in trades.to_dict("records"):
                        trade_rows.append(
                            {"route": route, "variant": variant, **row}
                        )
            for execution, slippage, lag in (
                ("stress_8bps", engine.STRESS_SLIPPAGE, 0),
                ("one_day_extra_delay", engine.BASE_SLIPPAGE, 1),
            ):
                result = run_strategy(
                    engine,
                    book,
                    features,
                    long_config,
                    short_config,
                    variant=variant,
                    start=0,
                    end=book.count,
                    slippage=slippage,
                    signal_lag=lag,
                )
                metric_rows.append(
                    {
                        "route": route,
                        "variant": variant,
                        "window": "full",
                        "execution": execution,
                        **result.metrics,
                        **trade_attribution(
                            annotate_trades(
                                result,
                                variant,
                                engine=engine,
                                book=book,
                                features=features,
                                short_config=short_config,
                                signal_lag=lag,
                            )
                        ),
                    }
                )
            for phase in PHASES:
                phase_book = route_books[route][phase]
                phase_result = run_strategy(
                    engine,
                    phase_book,
                    route_features[route][phase],
                    long_config,
                    short_config,
                    variant=variant,
                    start=0,
                    end=phase_book.count,
                    slippage=engine.BASE_SLIPPAGE,
                )
                phase_rows.append(
                    {
                        "route": route,
                        "variant": variant,
                        "phase_hours": phase,
                        **phase_result.metrics,
                    }
                )

    # Latest HYPE extension is reported separately from the common historical end.
    latest_book = hype_base.build_book(
        parent,
        hype_hourly,
        hype_quality,
        hype_funding,
        hype_funding_quality,
        phase_hours=0,
    )
    latest_features = engine.build_features(latest_book, hype_hourly, hype_funding)
    latest: dict[str, Any] = {}
    for variant in variants:
        latest_result = run_strategy(
            engine,
            latest_book,
            latest_features,
            *hype_configs,
            variant=variant,
            start=0,
            end=latest_book.count,
            slippage=engine.BASE_SLIPPAGE,
            retain=True,
        )
        latest[variant] = {
            "metrics": latest_result.metrics,
            "attribution": trade_attribution(
                annotate_trades(
                    latest_result,
                    variant,
                    engine=engine,
                    book=latest_book,
                    features=latest_features,
                    short_config=hype_configs[1],
                )
            ),
        }

    judgments: dict[str, Any] = {}
    metrics_frame = pd.DataFrame(metric_rows)
    for route in route_books:
        base = metrics_frame.loc[
            metrics_frame["route"].eq(route)
            & metrics_frame["variant"].eq("R0_baseline")
            & metrics_frame["window"].eq("full")
            & metrics_frame["execution"].eq("base_4bps")
        ].iloc[0]
        reversal = metrics_frame.loc[
            metrics_frame["route"].eq(route)
            & metrics_frame["variant"].eq("R1_long_exit_short_reversal")
            & metrics_frame["window"].eq("full")
            & metrics_frame["execution"].eq("base_4bps")
        ].iloc[0]
        base_stress = metrics_frame.loc[
            metrics_frame["route"].eq(route)
            & metrics_frame["variant"].eq("R0_baseline")
            & metrics_frame["window"].eq("full")
            & metrics_frame["execution"].eq("stress_8bps")
        ].iloc[0]
        reversal_stress = metrics_frame.loc[
            metrics_frame["route"].eq(route)
            & metrics_frame["variant"].eq("R1_long_exit_short_reversal")
            & metrics_frame["window"].eq("full")
            & metrics_frame["execution"].eq("stress_8bps")
        ].iloc[0]
        base_improved = reversal["net_return_pct"] > base["net_return_pct"]
        stress_improved = (
            reversal_stress["net_return_pct"] > base_stress["net_return_pct"]
        )
        mdd_ok = (
            reversal["max_drawdown_pct"] >= base["max_drawdown_pct"] - 5.0
        )
        forced_positive = reversal["forced_reversal_net_pnl"] > 0.0
        if base_improved and stress_improved and mdd_ok and forced_positive:
            verdict = "改善"
        elif not base_improved or not forced_positive:
            verdict = "失败"
        else:
            verdict = "混合"
        judgments[route] = {
            "verdict": verdict,
            "base_return_delta_pp": float(
                reversal["net_return_pct"] - base["net_return_pct"]
            ),
            "stress_return_delta_pp": float(
                reversal_stress["net_return_pct"]
                - base_stress["net_return_pct"]
            ),
            "mdd_delta_pp": float(
                reversal["max_drawdown_pct"] - base["max_drawdown_pct"]
            ),
            "forced_reversal_trades": int(reversal["forced_reversal_trades"]),
            "forced_reversal_net_pnl": float(
                reversal["forced_reversal_net_pnl"]
            ),
        }

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "contract": (
            "specs/binance-ma7-long-exit-short-reversal-contract-2026-08-06.md"
        ),
        "mechanism": (
            "on long ma7_hysteresis_exit, close long and open 1x short "
            "at the same next-day open; retain frozen short exits/protection"
        ),
        "pins": {
            "engine_sha256": ENGINE_SHA256,
            "transfer_sha256": TRANSFER_SHA256,
            "hype_config_summary_sha256": HYPE_SUMMARY_SHA256,
            "shared_config_summary_sha256": SHARED_SUMMARY_SHA256,
        },
        "configs": {
            "HYPE_V1": {
                "long": asdict(hype_configs[0]),
                "short": asdict(hype_configs[1]),
            },
            "BTC_ETH_shared": {
                "long": asdict(shared_configs[0]),
                "short": asdict(shared_configs[1]),
            },
        },
        "data_quality": data_quality,
        "primary": primary,
        "latest_hype_extension": latest,
        "judgments": judgments,
        "evidence_role": (
            "historical mechanism diagnostic; all history researcher-exposed; "
            "not clean OOS and not promotion evidence"
        ),
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_ma7_long_exit_short_reversal_{args.run_date}"
    metrics_frame.to_csv(ARTIFACT_DIR / f"{stem}_metrics.csv", index=False)
    pd.DataFrame(phase_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_phase.csv", index=False
    )
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent.csv", index=False
    )
    pd.DataFrame(trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades.csv", index=False
    )
    (ARTIFACT_DIR / f"{stem}_summary.json").write_text(
        json.dumps(clean(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(clean(judgments), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
