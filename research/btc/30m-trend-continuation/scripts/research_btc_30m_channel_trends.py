from __future__ import annotations

from dataclasses import asdict, dataclass, replace
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
FAMILY_DIR = ROOT / "research/btc/30m-trend-continuation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
HELPER_PATH = FAMILY_DIR / "scripts/research_btc_30m_trend_continuation.py"
HELPER_SHA256 = "c8dbe4fd8ca3d3b8c030c5cf87133b6bda1204dbad06cddf3966c249128cb5f7"
DATE = "2026-07-21"
SUMMARY_PATH = ARTIFACT_DIR / f"btc_30m_channel_trends_summary_{DATE}.json"
CANDIDATES_PATH = ARTIFACT_DIR / f"btc_30m_channel_trends_candidates_{DATE}.csv"
TRADES_PATH = ARTIFACT_DIR / f"btc_30m_channel_trends_selected_trades_{DATE}.csv"
WINDOWS_PATH = ARTIFACT_DIR / f"btc_30m_channel_trends_rolling_{DATE}.csv"

BREAKOUT_WINDOWS = (12, 24, 48, 96)
EMA_PAIRS = ((24, 96), (48, 192), (96, 384))
SLOPE_LAGS = (4, 8, 16)
VOLATILITY_MODES = ("none", "cap_0.005", "band_0.0015_0.0075")
VOLUME_MINS = (0.0, 1.0)
KELTNER_WINDOWS = (24, 48)
KELTNER_MULTIPLIERS = (1.5, 2.0, 2.5)
EXIT_PROFILES = tuple(
    (stop_atr, hold_bars)
    for stop_atr in (2.5, 3.0, 4.0, 5.0)
    for hold_bars in (24, 48, 96, 192)
)


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    channel: str
    channel_window: int
    channel_multiplier: float
    ema_fast: int
    ema_slow: int
    slope_lag: int
    volatility_mode: str
    volume_min: float
    stop_atr: float
    max_hold_bars: int


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


def load_helper() -> Any:
    actual = sha256_bytes(HELPER_PATH.read_bytes())
    if actual != HELPER_SHA256:
        raise RuntimeError(
            "BTC 30m helper SHA mismatch: "
            f"expected {HELPER_SHA256}, got {actual}"
        )
    module_name = "btc_30m_channel_trend_helper"
    spec = importlib.util.spec_from_file_location(module_name, HELPER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load helper: {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def signal_universe() -> list[ChannelConfig]:
    donchian = [
        ChannelConfig(
            channel="donchian",
            channel_window=window,
            channel_multiplier=0.0,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            slope_lag=slope_lag,
            volatility_mode=volatility_mode,
            volume_min=volume_min,
            stop_atr=4.0,
            max_hold_bars=96,
        )
        for (
            window,
            (ema_fast, ema_slow),
            slope_lag,
            volatility_mode,
            volume_min,
        ) in product(
            BREAKOUT_WINDOWS,
            EMA_PAIRS,
            SLOPE_LAGS,
            VOLATILITY_MODES,
            VOLUME_MINS,
        )
    ]
    keltner = [
        ChannelConfig(
            channel="keltner",
            channel_window=window,
            channel_multiplier=multiplier,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            slope_lag=8,
            volatility_mode=volatility_mode,
            volume_min=volume_min,
            stop_atr=4.0,
            max_hold_bars=96,
        )
        for (
            window,
            multiplier,
            (ema_fast, ema_slow),
            volatility_mode,
            volume_min,
        ) in product(
            KELTNER_WINDOWS,
            KELTNER_MULTIPLIERS,
            EMA_PAIRS,
            VOLATILITY_MODES,
            VOLUME_MINS,
        )
    ]
    return donchian + keltner


def base_features(base: Any, frame: pd.DataFrame) -> dict[str, Any]:
    close = frame["close"]
    ema_windows = sorted(
        {
            *[value for pair in EMA_PAIRS for value in pair],
            *KELTNER_WINDOWS,
        }
    )
    atr = base.wilder_atr(frame, 28)
    return {
        "atr": atr,
        "atr_pct": atr / close,
        "emas": {window: base.ema(close, window) for window in ema_windows},
        "donchian": {
            window: frame["high"].rolling(window, min_periods=window).max().shift(1)
            for window in BREAKOUT_WINDOWS
        },
        "rvol": (
            frame["volume"]
            / frame["volume"].rolling(48, min_periods=24).median().shift(1)
        ),
    }


def build_signals(
    frame: pd.DataFrame,
    features: dict[str, Any],
    config: ChannelConfig,
) -> tuple[np.ndarray, np.ndarray]:
    close = frame["close"]
    fast = features["emas"][config.ema_fast]
    slow = features["emas"][config.ema_slow]
    trend = close.gt(fast) & fast.gt(slow) & slow.gt(slow.shift(config.slope_lag))
    atr_pct = features["atr_pct"]
    if config.volatility_mode == "none":
        volatility = pd.Series(True, index=frame.index)
    elif config.volatility_mode == "cap_0.005":
        volatility = atr_pct.le(0.005)
    elif config.volatility_mode == "band_0.0015_0.0075":
        volatility = atr_pct.between(0.0015, 0.0075)
    else:
        raise ValueError(f"unknown volatility mode: {config.volatility_mode}")
    volume = (
        pd.Series(True, index=frame.index)
        if config.volume_min == 0.0
        else features["rvol"].ge(config.volume_min)
    )
    if config.channel == "donchian":
        upper = features["donchian"][config.channel_window]
    elif config.channel == "keltner":
        upper = (
            features["emas"][config.channel_window]
            + config.channel_multiplier * features["atr"]
        ).shift(1)
    else:
        raise ValueError(f"unknown channel: {config.channel}")
    crossed = close.gt(upper) & close.shift(1).le(upper.shift(1))
    long_signal = trend & volatility & volume & crossed
    return (
        long_signal.fillna(False).to_numpy(bool),
        np.zeros(len(frame), dtype=bool),
    )


def engine_config(base: Any, config: ChannelConfig, *, stress: bool = False) -> Any:
    signal = base.SignalConfig(
        compression_quantile=0.30,
        compression_lookback=8,
        breakout_window=48,
        ema_fast=48,
        ema_slow=192,
        slope_lag=8,
        atr_cap=0.01,
    )
    multiple = 2.0 if stress else 1.0
    return base.StrategyConfig(
        signal=signal,
        stop_atr=config.stop_atr,
        max_hold_bars=config.max_hold_bars,
        side_mode="long",
        fee_per_fill=base.FEE_PER_FILL * multiple,
        slippage_per_fill=base.SLIPPAGE_PER_FILL * multiple,
    )


def candidate_id(config: ChannelConfig) -> str:
    return "btc30-ct-" + sha256_bytes(canonical_json_bytes(asdict(config)))[:12]


def simulate_range(
    base: Any,
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    signals: tuple[np.ndarray, np.ndarray],
    config: ChannelConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    label: str,
    *,
    stress: bool = False,
) -> Any:
    return base.simulate(
        frame,
        funding_path,
        atr,
        signals[0],
        signals[1],
        engine_config(base, config, stress=stress),
        start,
        end,
        label=label,
    )


def evaluate(
    base: Any,
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    signals: tuple[np.ndarray, np.ndarray],
    config: ChannelConfig,
    *,
    run_stress: bool,
) -> dict[str, Any]:
    identifier = candidate_id(config)
    train = simulate_range(
        base,
        frame,
        funding_path,
        atr,
        signals,
        config,
        base.TRAIN_START,
        base.VALIDATION_START,
        f"{identifier}_train",
    ).metrics
    validation = simulate_range(
        base,
        frame,
        funding_path,
        atr,
        signals,
        config,
        base.VALIDATION_START,
        base.DIAGNOSTIC_START,
        f"{identifier}_validation",
    ).metrics
    development_pass, failures = base.development_gate(train, validation)
    stress_train: dict[str, Any] = {}
    stress_validation: dict[str, Any] = {}
    stress_pass = False
    if run_stress and development_pass:
        stress_train = simulate_range(
            base,
            frame,
            funding_path,
            atr,
            signals,
            config,
            base.TRAIN_START,
            base.VALIDATION_START,
            f"{identifier}_train_2x",
            stress=True,
        ).metrics
        stress_validation = simulate_range(
            base,
            frame,
            funding_path,
            atr,
            signals,
            config,
            base.VALIDATION_START,
            base.DIAGNOSTIC_START,
            f"{identifier}_validation_2x",
            stress=True,
        ).metrics
        stress_pass = (
            stress_train["return_pct"] > 0.0
            and stress_validation["return_pct"] > 0.0
        )
        if not stress_pass:
            failures.append("double_cost_return")
    return {
        "candidate_id": identifier,
        "config": asdict(config),
        "train": train,
        "validation": validation,
        "stress_2x_train": stress_train,
        "stress_2x_validation": stress_validation,
        "development_gate": development_pass,
        "stress_gate": stress_pass,
        "complete_gate": development_pass and stress_pass,
        "gate_failures": failures,
    }


def rank_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        min(row["train"]["return_pct"], row["validation"]["return_pct"]),
        min(row["train"]["profit_factor"], row["validation"]["profit_factor"]),
        -max(
            abs(row["train"]["max_drawdown_pct"]),
            abs(row["validation"]["max_drawdown_pct"]),
        ),
        min(row["train"]["trades"], row["validation"]["trades"]),
    )


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {
        "candidate_id": row["candidate_id"],
        **row["config"],
        "development_gate": row["development_gate"],
        "stress_gate": row["stress_gate"],
        "complete_gate": row["complete_gate"],
        "gate_failures": "|".join(row["gate_failures"]),
    }
    for split in ("train", "validation", "stress_2x_train", "stress_2x_validation"):
        for metric, value in row[split].items():
            output[f"{split}_{metric}"] = value
    for split in ("reused_diagnostic", "reused_diagnostic_2x_cost", "recent_1y"):
        for metric, value in row.get(split, {}).items():
            output[f"{split}_{metric}"] = value
    output["phase_gate_pass"] = row.get("phase_gate_pass", "")
    return output


def audit_metrics(
    base: Any,
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    config: ChannelConfig,
    end: pd.Timestamp,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    features = base_features(base, frame)
    atr = features["atr"].to_numpy(float)
    funding_path = base.funding_cumulative(frame.index, funding)
    signals = build_signals(frame, features, config)
    diagnostic = simulate_range(
        base,
        frame,
        funding_path,
        atr,
        signals,
        config,
        base.DIAGNOSTIC_START,
        end,
        "selected_diagnostic",
    )
    diagnostic_2x = simulate_range(
        base,
        frame,
        funding_path,
        atr,
        signals,
        config,
        base.DIAGNOSTIC_START,
        end,
        "selected_diagnostic_2x",
        stress=True,
    )
    recent = {
        name: simulate_range(
            base,
            frame,
            funding_path,
            atr,
            signals,
            config,
            max(base.TRAIN_START, end - delta),
            end,
            f"recent_{name}",
        ).metrics
        for name, delta in {
            "1d": pd.Timedelta(days=1),
            "7d": pd.Timedelta(days=7),
            "1m": pd.Timedelta(days=30),
            "3m": pd.Timedelta(days=90),
            "6m": pd.Timedelta(days=180),
            "1y": pd.Timedelta(days=365),
        }.items()
    }
    years = {
        str(year): simulate_range(
            base,
            frame,
            funding_path,
            atr,
            signals,
            config,
            pd.Timestamp(year=year, month=1, day=1, tz="UTC"),
            min(pd.Timestamp(year=year + 1, month=1, day=1, tz="UTC"), end),
            f"year_{year}",
        ).metrics
        for year in range(2020, end.year + 1)
    }
    rolling = base.rolling_windows(
        frame,
        funding_path,
        atr,
        signals,
        engine_config(base, config),
        end,
    )
    all_trades = pd.concat(
        [
            simulate_range(
                base,
                frame,
                funding_path,
                atr,
                signals,
                config,
                range_start,
                range_end,
                label,
            ).trades
            for range_start, range_end, label in (
                (base.TRAIN_START, base.VALIDATION_START, "selected_train"),
                (
                    base.VALIDATION_START,
                    base.DIAGNOSTIC_START,
                    "selected_validation",
                ),
                (base.DIAGNOSTIC_START, end, "selected_diagnostic"),
            )
        ],
        ignore_index=True,
    )
    metrics = {
        "reused_diagnostic": diagnostic.metrics,
        "reused_diagnostic_2x_cost": diagnostic_2x.metrics,
        "recent_slices": recent,
        "year_metrics": years,
        "rolling_180d": {
            "count": len(rolling),
            "positive_count": int((rolling["return_pct"] > 0.0).sum()),
            "positive_ratio": float((rolling["return_pct"] > 0.0).mean()),
        },
    }
    return metrics, rolling, all_trades


def phase_audit(
    helper: Any,
    base: Any,
    native_start: pd.Timestamp,
    native_end: pd.Timestamp,
    funding: pd.DataFrame,
    config: ChannelConfig,
) -> dict[str, Any]:
    source_15m = helper.load_15m_phase_source(base, native_start, native_end)
    frame = helper.aggregate_offset_30m(source_15m)
    end = frame.index[-1] + helper.BAR
    features = base_features(base, frame)
    atr = features["atr"].to_numpy(float)
    funding_path = base.funding_cumulative(frame.index, funding)
    signals = build_signals(frame, features, config)
    ranges = {
        "train": (base.TRAIN_START, base.VALIDATION_START),
        "validation": (base.VALIDATION_START, base.DIAGNOSTIC_START),
        "reused_diagnostic": (base.DIAGNOSTIC_START, end),
    }
    metrics = {
        name: simulate_range(
            base,
            frame,
            funding_path,
            atr,
            signals,
            config,
            start,
            range_end,
            f"phase15_{name}",
        ).metrics
        for name, (start, range_end) in ranges.items()
    }
    metrics["reused_diagnostic_2x_cost"] = simulate_range(
        base,
        frame,
        funding_path,
        atr,
        signals,
        config,
        base.DIAGNOSTIC_START,
        end,
        "phase15_diagnostic_2x",
        stress=True,
    ).metrics
    return {
        "range": [frame.index[0].isoformat(), end.isoformat()],
        "bar_count": len(frame),
        "aggregation": "audited native 15m aggregated to hh:15/hh:45 30m bars",
        "metrics": metrics,
        "phase_gate_pass": all(
            metrics[name]["return_pct"] > 0.0
            for name in (
                "train",
                "validation",
                "reused_diagnostic",
                "reused_diagnostic_2x_cost",
            )
        ),
        "source_audit_path": str(helper.SOURCE_15M_AUDIT.relative_to(ROOT)),
        "source_audit_sha256": sha256_bytes(helper.SOURCE_15M_AUDIT.read_bytes()),
        "derivation_formula_version": "btc-30m-offset15-ohlcv-v1",
        "null_policy": "drop groups without exactly two continuous 15m source bars",
        "fill_policy": "none",
    }


def main() -> None:
    helper = load_helper()
    base = helper.load_source()
    helper.configure(base)
    frame, funding, data_metadata = helper.load_30m_data(base)
    end = pd.Timestamp(data_metadata["end_exclusive"])
    features = base_features(base, frame)
    atr = features["atr"].to_numpy(float)
    funding_path = base.funding_cumulative(frame.index, funding)

    rows: list[dict[str, Any]] = []
    configs = signal_universe()
    for number, config in enumerate(configs, start=1):
        signals = build_signals(frame, features, config)
        row = evaluate(
            base,
            frame,
            funding_path,
            atr,
            signals,
            config,
            run_stress=True,
        )
        row["stage"] = "signal"
        rows.append(row)
        if number % 40 == 0:
            print(f"signal stage {number}/{len(configs)}", flush=True)

    complete_signals = [row for row in rows if row["complete_gate"]]
    development_signals = [row for row in rows if row["development_gate"]]
    parent_pool = complete_signals or development_signals or rows
    parents = sorted(parent_pool, key=rank_key, reverse=True)[:12]
    for parent in parents:
        parent_config = ChannelConfig(**parent["config"])
        signals = build_signals(frame, features, parent_config)
        for stop_atr, max_hold_bars in EXIT_PROFILES:
            config = replace(
                parent_config,
                stop_atr=stop_atr,
                max_hold_bars=max_hold_bars,
            )
            if config == parent_config:
                continue
            row = evaluate(
                base,
                frame,
                funding_path,
                atr,
                signals,
                config,
                run_stress=True,
            )
            row["stage"] = "exit"
            rows.append(row)

    complete = [row for row in rows if row["complete_gate"]]
    full_history_robust: list[dict[str, Any]] = []
    for number, row in enumerate(complete, start=1):
        config = ChannelConfig(**row["config"])
        signals = build_signals(frame, features, config)
        row["reused_diagnostic"] = simulate_range(
            base,
            frame,
            funding_path,
            atr,
            signals,
            config,
            base.DIAGNOSTIC_START,
            end,
            f"{row['candidate_id']}_diagnostic",
        ).metrics
        row["reused_diagnostic_2x_cost"] = simulate_range(
            base,
            frame,
            funding_path,
            atr,
            signals,
            config,
            base.DIAGNOSTIC_START,
            end,
            f"{row['candidate_id']}_diagnostic_2x",
            stress=True,
        ).metrics
        row["recent_1y"] = simulate_range(
            base,
            frame,
            funding_path,
            atr,
            signals,
            config,
            end - pd.Timedelta(days=365),
            end,
            f"{row['candidate_id']}_recent_1y",
        ).metrics
        if (
            row["reused_diagnostic"]["return_pct"] > 0.0
            and row["reused_diagnostic_2x_cost"]["return_pct"] > 0.0
            and row["recent_1y"]["return_pct"] > -5.0
        ):
            full_history_robust.append(row)
        if number % 40 == 0:
            print(f"diagnostic stage {number}/{len(complete)}", flush=True)

    def full_history_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
        return (
            min(
                row["train"]["return_pct"],
                row["validation"]["return_pct"],
                row["reused_diagnostic"]["return_pct"],
            ),
            min(
                row["stress_2x_train"]["return_pct"],
                row["stress_2x_validation"]["return_pct"],
                row["reused_diagnostic_2x_cost"]["return_pct"],
            ),
            row["recent_1y"]["return_pct"],
            -abs(row["reused_diagnostic"]["max_drawdown_pct"]),
        )

    phase_selected: dict[str, Any] | None = None
    phase: dict[str, Any] | None = None
    for row in sorted(full_history_robust, key=full_history_key, reverse=True)[:16]:
        config = ChannelConfig(**row["config"])
        candidate_phase = phase_audit(
            helper,
            base,
            pd.Timestamp(data_metadata["start"]),
            end,
            funding,
            config,
        )
        row["phase_gate_pass"] = candidate_phase["phase_gate_pass"]
        if candidate_phase["phase_gate_pass"]:
            phase_selected = row
            phase = candidate_phase
            break

    selected = phase_selected or max(
        full_history_robust or complete or rows,
        key=full_history_key if full_history_robust else rank_key,
    )
    selected_config = ChannelConfig(**selected["config"])
    audit, rolling, trades = audit_metrics(
        base,
        frame,
        funding,
        selected_config,
        end,
    )
    if phase is None:
        phase = phase_audit(
            helper,
            base,
            pd.Timestamp(data_metadata["start"]),
            end,
            funding,
            selected_config,
        )
    rolling_ratio = audit["rolling_180d"]["positive_ratio"]
    positive_years = sum(
        metrics["return_pct"] > 0.0
        for metrics in audit["year_metrics"].values()
    )
    research_candidate = bool(
        selected["complete_gate"]
        and audit["reused_diagnostic"]["return_pct"] > 0.0
        and audit["reused_diagnostic_2x_cost"]["return_pct"] > 0.0
        and audit["recent_slices"]["1y"]["return_pct"] > 0.0
        and rolling_ratio >= 0.55
        and positive_years >= 4
        and phase["phase_gate_pass"]
    )

    atomic_write_csv(
        CANDIDATES_PATH,
        pd.DataFrame([flatten(row) for row in sorted(rows, key=rank_key, reverse=True)]),
    )
    atomic_write_csv(WINDOWS_PATH, rolling)
    atomic_write_csv(TRADES_PATH, trades)
    script_path = Path(__file__).resolve()
    summary = {
        "family": "BTC-30M-Trend-Continuation",
        "research_identity": "BTC-30M-CHANNEL-TRENDS-2026-07-21",
        "status": "explore / not promoted / not live-ready",
        "research_role": (
            "full-history research candidate; prospective OOS required"
            if research_candidate
            else "failed diagnostic"
        ),
        "research_candidate": research_candidate,
        "data": data_metadata,
        "splits": {
            "train": [base.TRAIN_START.isoformat(), base.VALIDATION_START.isoformat()],
            "validation": [
                base.VALIDATION_START.isoformat(),
                base.DIAGNOSTIC_START.isoformat(),
            ],
            "reused_diagnostic": [base.DIAGNOSTIC_START.isoformat(), end.isoformat()],
            "prospective_oos_start": end.isoformat(),
        },
        "contamination_disclosure": (
            "30m parameters were selected on train/validation only, then audited on "
            "2024 onward. The mechanism was informed by prior 15m BTC research, so "
            "the reused diagnostic is not claimed as untouched OOS."
        ),
        "execution": {
            "entry": "closed native 30m signal, next native 30m open",
            "stop": "entry-bar active, gap-aware, adverse slippage",
            "time_exit": "max_hold reached at 30m bar open",
            "fee_per_fill": base.FEE_PER_FILL,
            "adverse_slippage_per_fill": base.SLIPPAGE_PER_FILL,
            "funding": "official audited historical events",
            "allocation": 1.0,
        },
        "universe": {
            "signal_count": len(configs),
            "signal_development_gate_count": len(development_signals),
            "signal_complete_gate_count": len(complete_signals),
            "exit_parent_count": len(parents),
            "total_evaluated": len(rows),
            "complete_gate_count": len(complete),
            "full_history_robust_count": len(full_history_robust),
            "breakout_windows": BREAKOUT_WINDOWS,
            "ema_pairs": EMA_PAIRS,
            "slope_lags": SLOPE_LAGS,
            "volatility_modes": VOLATILITY_MODES,
            "volume_mins": VOLUME_MINS,
            "keltner_windows": KELTNER_WINDOWS,
            "keltner_multipliers": KELTNER_MULTIPLIERS,
            "exit_profiles": EXIT_PROFILES,
        },
        "selected": selected,
        "selection_disclosure": (
            "Signal and exit parameters first passed train/validation and 2x-cost "
            "gates. Reused diagnostic, recent 1y, and offset-phase results were then "
            "used to choose among survivors, so this is explicitly full-history "
            "research selection rather than untouched OOS."
        ),
        **audit,
        "phase_alignment_audit": phase,
        "positive_year_count": positive_years,
        "remaining_blockers": [
            "no untouched historical OOS; prospective evidence begins at frozen end",
            "CPCV, trade-block bootstrap, and runner state-machine audit not completed",
        ],
        "artifacts": {
            "candidates": str(CANDIDATES_PATH.relative_to(ROOT)),
            "trades": str(TRADES_PATH.relative_to(ROOT)),
            "rolling_windows": str(WINDOWS_PATH.relative_to(ROOT)),
        },
        "provenance": {
            "formula_version": "btc-30m-channel-trends-v1",
            "generation_time_utc": datetime.now(timezone.utc).isoformat(),
            "code_path": str(script_path.relative_to(ROOT)),
            "code_sha256": sha256_bytes(script_path.read_bytes()),
            "helper_path": str(HELPER_PATH.relative_to(ROOT)),
            "helper_sha256": HELPER_SHA256,
            "source_columns": [
                "ts",
                "open",
                "high",
                "low",
                "close",
                "volume",
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
                    "selected": selected,
                    **audit,
                    "phase_alignment_audit": phase,
                    "universe": summary["universe"],
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
