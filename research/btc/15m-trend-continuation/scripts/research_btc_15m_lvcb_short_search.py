from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.util
from itertools import product
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/15m-trend-continuation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SOURCE_PATH = FAMILY_DIR / "scripts/research_btc_15m_low_vol_compression_breakout.py"
SOURCE_SHA256 = "581326b35f376a4e5d397bd8255dad0425eab763939f707f5ed1eaf7b1c3c026"
DATE = "2026-07-21"
SUMMARY_PATH = ARTIFACT_DIR / f"btc_15m_lvcb_short_search_summary_{DATE}.json"
CANDIDATES_PATH = ARTIFACT_DIR / f"btc_15m_lvcb_short_search_candidates_{DATE}.csv"
TRADES_PATH = ARTIFACT_DIR / f"btc_15m_lvcb_short_search_trades_{DATE}.csv"
WINDOWS_PATH = ARTIFACT_DIR / f"btc_15m_lvcb_short_search_rolling_{DATE}.csv"

COMPRESSION_QUANTILES = (0.20, 0.30, 0.40, 0.50)
COMPRESSION_LOOKBACKS = (8, 16, 32)
BREAKOUT_WINDOWS = (48, 96, 192)
EMA_PAIRS = ((48, 192), (96, 384))
SLOPE_LAGS = (8, 16)
ATR_CAPS = (0.0030, 0.0035, 0.0040, 0.0050)
EXIT_PROFILES = tuple(
    (stop_atr, max_hold_bars)
    for stop_atr in (2.0, 3.0, 4.0, 5.0, 6.0)
    for max_hold_bars in (48, 96, 192, 384)
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def finite(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isfinite(number):
            return number
        return "inf" if number > 0 else "-inf"
    return value


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    complete = finite(payload)
    body = {key: value for key, value in complete.items() if key != "payload_sha256"}
    complete["payload_sha256"] = sha256_bytes(canonical_json_bytes(body))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(complete, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def load_source() -> Any:
    actual = sha256_bytes(SOURCE_PATH.read_bytes())
    if actual != SOURCE_SHA256:
        raise RuntimeError(
            "BTC 15m LVCB source SHA mismatch: "
            f"expected {SOURCE_SHA256}, got {actual}"
        )
    module_name = "btc_15m_lvcb_short_search_source"
    spec = importlib.util.spec_from_file_location(module_name, SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load source: {SOURCE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def configure_source(source: Any) -> None:
    source.COMPRESSION_QUANTILES = COMPRESSION_QUANTILES
    source.COMPRESSION_LOOKBACKS = COMPRESSION_LOOKBACKS
    source.BREAKOUT_WINDOWS = BREAKOUT_WINDOWS
    source.EMA_PAIRS = EMA_PAIRS
    source.SLOPE_LAGS = SLOPE_LAGS
    source.ATR_CAPS = ATR_CAPS


def signal_universe(source: Any) -> list[Any]:
    return [
        source.SignalConfig(
            compression_quantile=quantile,
            compression_lookback=lookback,
            breakout_window=breakout,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            slope_lag=slope_lag,
            atr_cap=atr_cap,
        )
        for (
            quantile,
            lookback,
            breakout,
            (ema_fast, ema_slow),
            slope_lag,
            atr_cap,
        ) in product(
            COMPRESSION_QUANTILES,
            COMPRESSION_LOOKBACKS,
            BREAKOUT_WINDOWS,
            EMA_PAIRS,
            SLOPE_LAGS,
            ATR_CAPS,
        )
    ]


def evaluate_deferred_stress(
    source: Any,
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    signals: tuple[np.ndarray, np.ndarray],
    config: Any,
    end: pd.Timestamp,
) -> dict[str, Any]:
    row = source.evaluate(
        frame,
        funding_path,
        atr,
        signals,
        config,
        end,
        run_stress=False,
    )
    if row["development_gate"]:
        row = source.evaluate(
            frame,
            funding_path,
            atr,
            signals,
            config,
            end,
            run_stress=True,
        )
    return row


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {
        "strategy_id": row["strategy_id"],
        "stage": row["stage"],
        "config_json": json.dumps(row["config"], sort_keys=True),
        "development_gate": row["development_gate"],
        "stress_gate": row["stress_gate"],
        "complete_gate": row["complete_gate"],
        "gate_failures": "|".join(row["gate_failures"]),
    }
    for split in (
        "train",
        "validation",
        "stress_2x_train",
        "stress_2x_validation",
    ):
        for metric, value in row.get(split, {}).items():
            output[f"{split}_{metric}"] = value
    return output


def simulate_range(
    source: Any,
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    signals: tuple[np.ndarray, np.ndarray],
    config: Any,
    start: pd.Timestamp,
    end: pd.Timestamp,
    label: str,
) -> Any:
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
    )


def main() -> None:
    source = load_source()
    configure_source(source)
    frame, funding, data_metadata = source.load_data()
    end = pd.Timestamp(data_metadata["end_exclusive"])
    features = source.base_features(frame)
    atr = features["atr"].to_numpy(float)
    funding_path = source.funding_cumulative(frame.index, funding)

    rows: list[dict[str, Any]] = []
    signals_by_id: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    universe = signal_universe(source)
    for number, signal_config in enumerate(universe, start=1):
        signals = source.build_signals(frame, features, signal_config)
        config = source.StrategyConfig(
            signal=signal_config,
            stop_atr=4.0,
            max_hold_bars=192,
            side_mode="short",
        )
        row = evaluate_deferred_stress(
            source,
            frame,
            funding_path,
            atr,
            signals,
            config,
            end,
        )
        row["stage"] = "signal"
        rows.append(row)
        signals_by_id[source.strategy_id(config)] = signals
        if number % 48 == 0:
            print(f"short signal stage {number}/{len(universe)}", flush=True)

    complete_signals = [row for row in rows if row["complete_gate"]]
    development_signals = [row for row in rows if row["development_gate"]]
    parent_pool = complete_signals or development_signals or rows
    parents = sorted(parent_pool, key=source.rank_key, reverse=True)[:12]
    for parent in parents:
        signal_config = source.SignalConfig(**parent["config"]["signal"])
        base_config = source.StrategyConfig(
            signal=signal_config,
            stop_atr=parent["config"]["stop_atr"],
            max_hold_bars=parent["config"]["max_hold_bars"],
            side_mode="short",
        )
        signals = signals_by_id.get(source.strategy_id(base_config))
        if signals is None:
            signals = source.build_signals(frame, features, signal_config)
        for stop_atr, max_hold_bars in EXIT_PROFILES:
            config = replace(
                base_config,
                stop_atr=stop_atr,
                max_hold_bars=max_hold_bars,
            )
            if config == base_config:
                continue
            row = evaluate_deferred_stress(
                source,
                frame,
                funding_path,
                atr,
                signals,
                config,
                end,
            )
            row["stage"] = "exit"
            rows.append(row)

    complete = [row for row in rows if row["complete_gate"]]
    selected = max(complete or rows, key=source.rank_key)
    selected_config = source.StrategyConfig(
        signal=source.SignalConfig(**selected["config"]["signal"]),
        stop_atr=selected["config"]["stop_atr"],
        max_hold_bars=selected["config"]["max_hold_bars"],
        side_mode="short",
    )
    selected_signals = source.build_signals(
        frame,
        features,
        selected_config.signal,
    )

    diagnostic = simulate_range(
        source,
        frame,
        funding_path,
        atr,
        selected_signals,
        selected_config,
        source.DIAGNOSTIC_START,
        end,
        "selected_short_diagnostic",
    )
    diagnostic_2x = simulate_range(
        source,
        frame,
        funding_path,
        atr,
        selected_signals,
        replace(
            selected_config,
            fee_per_fill=source.FEE_PER_FILL * 2.0,
            slippage_per_fill=source.SLIPPAGE_PER_FILL * 2.0,
        ),
        source.DIAGNOSTIC_START,
        end,
        "selected_short_diagnostic_2x",
    )
    long_ablation = simulate_range(
        source,
        frame,
        funding_path,
        atr,
        selected_signals,
        replace(selected_config, side_mode="long"),
        source.DIAGNOSTIC_START,
        end,
        "selected_signal_long_ablation",
    )
    both_ablation = simulate_range(
        source,
        frame,
        funding_path,
        atr,
        selected_signals,
        replace(selected_config, side_mode="both"),
        source.DIAGNOSTIC_START,
        end,
        "selected_signal_both_ablation",
    )
    rolling = source.rolling_windows(
        frame,
        funding_path,
        atr,
        selected_signals,
        selected_config,
        end,
    )
    recent = source.recent_slices(
        frame,
        funding_path,
        atr,
        selected_signals,
        selected_config,
        end,
    )
    years: dict[str, Any] = {}
    for year in range(2020, end.year + 1):
        year_start = pd.Timestamp(year=year, month=1, day=1, tz="UTC")
        year_end = min(
            pd.Timestamp(year=year + 1, month=1, day=1, tz="UTC"),
            end,
        )
        years[str(year)] = simulate_range(
            source,
            frame,
            funding_path,
            atr,
            selected_signals,
            selected_config,
            year_start,
            year_end,
            f"short_year_{year}",
        ).metrics

    all_trades = pd.concat(
        [
            simulate_range(
                source,
                frame,
                funding_path,
                atr,
                selected_signals,
                selected_config,
                start,
                range_end,
                label,
            ).trades
            for start, range_end, label in (
                (
                    source.TRAIN_START,
                    source.VALIDATION_START,
                    "selected_short_train",
                ),
                (
                    source.VALIDATION_START,
                    source.DIAGNOSTIC_START,
                    "selected_short_validation",
                ),
                (
                    source.DIAGNOSTIC_START,
                    end,
                    "selected_short_diagnostic",
                ),
            )
        ],
        ignore_index=True,
    )
    rolling_positive_ratio = float((rolling["return_pct"] > 0.0).mean())
    positive_year_count = sum(
        metrics["return_pct"] > 0.0 for metrics in years.values()
    )
    research_candidate = bool(
        selected["complete_gate"]
        and diagnostic.metrics["return_pct"] > 0.0
        and diagnostic_2x.metrics["return_pct"] > 0.0
        and recent["1y"]["return_pct"] > -5.0
        and rolling_positive_ratio > 0.50
        and positive_year_count >= 4
    )

    atomic_write_csv(
        CANDIDATES_PATH,
        pd.DataFrame(
            [
                flatten(row)
                for row in sorted(rows, key=source.rank_key, reverse=True)
            ]
        ),
    )
    atomic_write_csv(TRADES_PATH, all_trades)
    atomic_write_csv(WINDOWS_PATH, rolling)
    script_path = Path(__file__).resolve()
    summary = {
        "family": "BTC-15M-Trend-Continuation",
        "research_identity": "BTC-15M-LVCB-SHORT-SEARCH-2026-07-21",
        "status": "explore / not promoted / not live-ready",
        "research_role": (
            "short-only full-history research candidate; prospective OOS required"
            if research_candidate
            else "failed short-only diagnostic"
        ),
        "research_candidate": research_candidate,
        "data": data_metadata,
        "splits": {
            "train": [
                source.TRAIN_START.isoformat(),
                source.VALIDATION_START.isoformat(),
            ],
            "validation": [
                source.VALIDATION_START.isoformat(),
                source.DIAGNOSTIC_START.isoformat(),
            ],
            "reused_diagnostic": [
                source.DIAGNOSTIC_START.isoformat(),
                end.isoformat(),
            ],
            "short_prospective_oos_start": end.isoformat(),
        },
        "selection_protocol": (
            "Short signal and exit parameters were ranked only on train/validation "
            "after development and 2x-cost gates. Reused diagnostic and recent "
            "slices were revealed once for the selected configuration."
        ),
        "contamination_disclosure": (
            "The short mechanism is a direction-specific extension of an existing "
            "full-history-designed LVCB family. No historical segment is claimed as "
            "untouched OOS; only data after short_prospective_oos_start is fresh."
        ),
        "execution": {
            "entry": "closed 15m short signal, next 15m open",
            "stop": "entry-bar active, gap-aware, adverse slippage",
            "time_exit": "max_hold reached at 15m bar open",
            "fee_per_fill": source.FEE_PER_FILL,
            "adverse_slippage_per_fill": source.SLIPPAGE_PER_FILL,
            "funding": "official audited historical events",
            "allocation": 1.0,
            "side_mode": "short",
        },
        "universe": {
            "signal_count": len(universe),
            "signal_development_gate_count": len(development_signals),
            "signal_complete_gate_count": len(complete_signals),
            "exit_parent_count": len(parents),
            "total_evaluated": len(rows),
            "complete_gate_count": len(complete),
            "compression_quantiles": COMPRESSION_QUANTILES,
            "compression_lookbacks": COMPRESSION_LOOKBACKS,
            "breakout_windows": BREAKOUT_WINDOWS,
            "ema_pairs": EMA_PAIRS,
            "slope_lags": SLOPE_LAGS,
            "atr_caps": ATR_CAPS,
            "exit_profiles": EXIT_PROFILES,
        },
        "selected": selected,
        "reused_diagnostic": diagnostic.metrics,
        "reused_diagnostic_2x_cost": diagnostic_2x.metrics,
        "direction_ablation": {
            "short_only": diagnostic.metrics,
            "long_only_same_signal": long_ablation.metrics,
            "both_same_signal": both_ablation.metrics,
        },
        "recent_slices": recent,
        "year_metrics": years,
        "rolling_180d": {
            "count": len(rolling),
            "positive_count": int((rolling["return_pct"] > 0.0).sum()),
            "positive_ratio": rolling_positive_ratio,
        },
        "positive_year_count": positive_year_count,
        "remaining_blockers": [
            "no untouched historical OOS; short prospective begins at frozen end",
            "BTC 1m data absent, so 15m phase gate is incomplete",
            "CPCV, bar-path Monte Carlo, and runner audit not completed",
        ],
        "artifacts": {
            "candidates": str(CANDIDATES_PATH.relative_to(ROOT)),
            "trades": str(TRADES_PATH.relative_to(ROOT)),
            "rolling_windows": str(WINDOWS_PATH.relative_to(ROOT)),
        },
        "provenance": {
            "formula_version": "btc-15m-lvcb-short-v1-search",
            "generation_time_utc": datetime.now(timezone.utc).isoformat(),
            "code_path": str(script_path.relative_to(ROOT)),
            "code_sha256": sha256_bytes(script_path.read_bytes()),
            "engine_path": str(SOURCE_PATH.relative_to(ROOT)),
            "engine_sha256": SOURCE_SHA256,
            "source_columns": [
                "ts",
                "open",
                "high",
                "low",
                "close",
                "funding_rate",
            ],
            "null_policy": "rolling warmup nulls suppress signals",
            "fill_policy": "none",
        },
    }
    atomic_write_json(SUMMARY_PATH, summary)
    print(
        json.dumps(
            finite(
                {
                    "research_candidate": research_candidate,
                    "universe": summary["universe"],
                    "selected": selected,
                    "reused_diagnostic": diagnostic.metrics,
                    "reused_diagnostic_2x_cost": diagnostic_2x.metrics,
                    "recent_slices": recent,
                    "year_metrics": years,
                    "rolling_180d": summary["rolling_180d"],
                    "direction_ablation": summary["direction_ablation"],
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
