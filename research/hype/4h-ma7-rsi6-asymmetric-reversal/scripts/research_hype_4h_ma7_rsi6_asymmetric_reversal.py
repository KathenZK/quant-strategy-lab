from __future__ import annotations

import argparse
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
FAMILY_DIR = ROOT / "research/hype/4h-ma7-rsi6-asymmetric-reversal"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BACKTEST_ENGINE = (
    ROOT
    / "research/hype/4h-ma7-close-reversal/scripts"
    / "research_hype_4h_ma7_close_reversal.py"
)
BACKTEST_ENGINE_SHA256 = (
    "e371ebd3a480ac3102401ee57cedf387a908aeb1238ad2bafc66ad4b1903d291"
)

FAMILY = "HYPE-4H-MA7-RSI6-Asymmetric-Reversal"
ALIAS = "HYPE-4H-MA7-RSI6-AR"
MA_WINDOW = 7
RSI_WINDOW = 6
OVERBOUGHT = 70.0
OVERSOLD = 30.0
OVERBOUGHT_MEMORY = 3
PHASES = (0, 1, 2, 3)
FEE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
VARIANT_BASELINE = "baseline"
VARIANT_CROSS_REENTRY = "cross_reentry"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest HYPE 4h SMA7 and RSI6 asymmetric reversal."
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument(
        "--variant",
        choices=(VARIANT_BASELINE, VARIANT_CROSS_REENTRY),
        default=VARIANT_BASELINE,
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


def wilder_rsi(close: np.ndarray, window: int = RSI_WINDOW) -> np.ndarray:
    values = np.asarray(close, dtype=float)
    output = np.full(len(values), np.nan, dtype=float)
    if len(values) <= window:
        return output
    delta = np.diff(values)
    gains = np.maximum(delta, 0.0)
    losses = np.maximum(-delta, 0.0)
    average_gain = float(gains[:window].mean())
    average_loss = float(losses[:window].mean())

    def rsi_value(gain: float, loss: float) -> float:
        if math.isclose(loss, 0.0, abs_tol=1e-15):
            return 50.0 if math.isclose(gain, 0.0, abs_tol=1e-15) else 100.0
        if math.isclose(gain, 0.0, abs_tol=1e-15):
            return 0.0
        relative_strength = gain / loss
        return 100.0 - 100.0 / (1.0 + relative_strength)

    output[window] = rsi_value(average_gain, average_loss)
    for index in range(window + 1, len(values)):
        gain = float(gains[index - 1])
        loss = float(losses[index - 1])
        average_gain = (
            average_gain * (window - 1) + gain
        ) / window
        average_loss = (
            average_loss * (window - 1) + loss
        ) / window
        output[index] = rsi_value(average_gain, average_loss)
    return output


def strategy_targets_from_arrays(
    close: np.ndarray,
    sma7: np.ndarray,
    rsi6: np.ndarray,
    *,
    start_index: int = 0,
    short_cross_reentry: bool = False,
) -> tuple[np.ndarray, list[str]]:
    if not (len(close) == len(sma7) == len(rsi6)):
        raise ValueError("indicator arrays must have equal length")
    targets = np.zeros(len(close), dtype=np.int8)
    transitions = ["hold"] * len(close)
    state = 0
    for index in range(start_index, len(close)):
        price = float(close[index])
        average = float(sma7[index])
        rsi = float(rsi6[index])
        old_state = state
        if state == 0:
            if math.isfinite(average) and price > average:
                state = 1
        elif state == 1:
            memory_start = max(0, index - OVERBOUGHT_MEMORY + 1)
            memory = rsi6[memory_start : index + 1]
            overbought_recently = bool(
                np.isfinite(memory).any()
                and np.nanmax(memory) > OVERBOUGHT
            )
            if (
                math.isfinite(average)
                and price < average
                and overbought_recently
            ):
                state = -1
        else:
            if (
                short_cross_reentry
                and math.isfinite(average)
                and price > average
            ):
                state = 1
            elif math.isfinite(rsi) and rsi < OVERSOLD:
                state = 0
        targets[index] = state
        if old_state == 0 and state == 1:
            transitions[index] = "flat_to_long"
        elif old_state == 1 and state == -1:
            transitions[index] = "long_to_short"
        elif old_state == -1 and state == 0:
            transitions[index] = "short_to_flat"
        elif old_state == -1 and state == 1:
            transitions[index] = "short_to_long"
    return targets, transitions


def build_strategy(
    engine: Any,
    bundle: Any,
    *,
    start_index: int = 0,
    variant: str = VARIANT_BASELINE,
) -> dict[str, Any]:
    close = bundle.bars["close"].to_numpy("float64")
    sma7 = (
        pd.Series(close, dtype=float)
        .rolling(MA_WINDOW, min_periods=MA_WINDOW)
        .mean()
        .to_numpy("float64")
    )
    rsi6 = wilder_rsi(close)
    targets, transitions = strategy_targets_from_arrays(
        close,
        sma7,
        rsi6,
        start_index=start_index,
        short_cross_reentry=variant == VARIANT_CROSS_REENTRY,
    )
    rsi_max3 = (
        pd.Series(rsi6, dtype=float)
        .rolling(OVERBOUGHT_MEMORY, min_periods=1)
        .max()
        .to_numpy("float64")
    )
    return {
        "targets": targets,
        "transitions": transitions,
        "sma7": sma7,
        "rsi6": rsi6,
        "rsi_max3": rsi_max3,
        "engine": engine,
    }


def run_strategy(
    engine: Any,
    bundle: Any,
    *,
    start_index: int,
    terminal_index: int,
    fee: float = FEE,
    slippage: float = BASE_SLIPPAGE,
    signal_lag: int = 0,
    retain: bool = False,
    variant: str = VARIANT_BASELINE,
) -> tuple[Any, dict[str, Any]]:
    strategy = build_strategy(
        engine,
        bundle,
        start_index=start_index,
        variant=variant,
    )
    result = engine.backtest(
        bundle,
        route="external",
        start_index=start_index,
        terminal_index=terminal_index,
        fee=fee,
        slippage=slippage,
        signal_lag=signal_lag,
        retain=retain,
        external_targets=strategy["targets"],
    )
    executed_end = max(
        start_index,
        terminal_index - 1 - signal_lag,
    )
    executed_transitions = strategy["transitions"][
        start_index:executed_end
    ]
    strategy["transition_counts"] = {
        name: executed_transitions.count(name)
        for name in (
            "flat_to_long",
            "long_to_short",
            "short_to_flat",
            "short_to_long",
        )
    }
    result.metrics["strategy"] = (
        ALIAS
        if variant == VARIANT_BASELINE
        else f"{ALIAS}-V2-OBS"
    )
    result.metrics["transition_counts"] = strategy["transition_counts"]
    return result, strategy


def rolling_90d(
    engine: Any,
    bundle: Any,
    *,
    variant: str = VARIANT_BASELINE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    window_bars = 90 * 24 // engine.BAR_HOURS
    step_bars = 30 * 24 // engine.BAR_HOURS
    start = 0
    while start + window_bars <= bundle.count:
        end = start + window_bars
        result, strategy = run_strategy(
            engine,
            bundle,
            start_index=start,
            terminal_index=end,
            variant=variant,
        )
        rows.append(
            {
                "window_index": len(rows),
                **result.metrics,
                **strategy["transition_counts"],
            }
        )
        start += step_bars
    return rows


def phase_audit(
    engine: Any,
    bundles: dict[int, Any],
    *,
    variant: str = VARIANT_BASELINE,
) -> list[dict[str, Any]]:
    common_start = max(
        pd.Timestamp(bundle.bars.iloc[0]["ts"])
        for bundle in bundles.values()
    )
    common_end = min(bundle.terminal_ts for bundle in bundles.values())
    rows: list[dict[str, Any]] = []
    for phase, bundle in sorted(bundles.items()):
        timestamps = pd.DatetimeIndex(
            [*bundle.bars["ts"], bundle.terminal_ts]
        )
        start = int(timestamps.searchsorted(common_start, side="left"))
        end = int(timestamps.searchsorted(common_end, side="right") - 1)
        result, strategy = run_strategy(
            engine,
            bundle,
            start_index=start,
            terminal_index=end,
            variant=variant,
        )
        rows.append(
            {
                "phase_hours": phase,
                "common_start": common_start.isoformat(),
                "common_end": common_end.isoformat(),
                **result.metrics,
                **strategy["transition_counts"],
            }
        )
    return rows


def trade_components(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(trades)
    rows: list[dict[str, Any]] = []
    for side in ("long", "short"):
        part = frame.loc[frame["side"].eq(side)].copy()
        positive = float(part.loc[part["net_pnl"].gt(0.0), "net_pnl"].sum())
        negative = float(-part.loc[part["net_pnl"].lt(0.0), "net_pnl"].sum())
        rows.append(
            {
                "side": side,
                "trades": len(part),
                "wins": int(part["net_pnl"].gt(0.0).sum()),
                "win_rate": (
                    float(part["net_pnl"].gt(0.0).mean())
                    if len(part)
                    else math.nan
                ),
                "net_pnl": float(part["net_pnl"].sum()),
                "profit_factor": (
                    positive / negative
                    if negative > 0.0
                    else (math.inf if positive > 0.0 else math.nan)
                ),
                "median_holding_hours": (
                    float(part["holding_hours"].median())
                    if len(part)
                    else math.nan
                ),
            }
        )
    return rows


def write_outputs(
    *,
    engine: Any,
    bundles: dict[int, Any],
    run_date: str,
    variant: str = VARIANT_BASELINE,
) -> None:
    bundle = bundles[0]
    audit_split = bundle.terminal_ts - pd.Timedelta(days=120)
    split_index = int(
        pd.DatetimeIndex(bundle.bars["ts"]).searchsorted(
            audit_split,
            side="left",
        )
    )
    if (
        split_index <= 0
        or split_index >= bundle.count
        or pd.Timestamp(bundle.bars.iloc[split_index]["ts"]) != audit_split
    ):
        raise RuntimeError("exact 120d audit split unavailable")
    scenarios = {
        "base": {
            "fee": FEE,
            "slippage": BASE_SLIPPAGE,
            "signal_lag": 0,
        },
        "stress_8bps": {
            "fee": FEE,
            "slippage": STRESS_SLIPPAGE,
            "signal_lag": 0,
        },
        "delay_1bar": {
            "fee": FEE,
            "slippage": BASE_SLIPPAGE,
            "signal_lag": 1,
        },
        "gross_no_trade_cost": {
            "fee": 0.0,
            "slippage": 0.0,
            "signal_lag": 0,
        },
    }
    windows = {
        "early": (0, split_index),
        "last_120d": (split_index, bundle.count),
        "full": (0, bundle.count),
    }
    audits: dict[str, Any] = {}
    metric_rows: list[dict[str, Any]] = []
    full_result: Any | None = None
    full_strategy: dict[str, Any] | None = None
    for window, (start, end) in windows.items():
        audits[window] = {}
        for scenario, kwargs in scenarios.items():
            retain = window == "full" and scenario == "base"
            result, strategy = run_strategy(
                engine,
                bundle,
                start_index=start,
                terminal_index=end,
                retain=retain,
                variant=variant,
                **kwargs,
            )
            audits[window][scenario] = result.metrics
            metric_rows.append(
                {
                    "window": window,
                    "scenario": scenario,
                    **result.metrics,
                }
            )
            if retain:
                full_result = result
                full_strategy = strategy
        benchmark = engine.backtest(
            bundle,
            route="buy_and_hold",
            start_index=start,
            terminal_index=end,
        )
        audits[window]["buy_and_hold"] = benchmark.metrics
        metric_rows.append(
            {
                "window": window,
                "scenario": "buy_and_hold",
                **benchmark.metrics,
            }
        )
    if full_result is None or full_strategy is None:
        raise RuntimeError("retained full strategy missing")

    phases = phase_audit(engine, bundles, variant=variant)
    rolling = rolling_90d(engine, bundle, variant=variant)
    recent = engine.recent_slices(full_result)
    components = trade_components(full_result.trades)
    full_base = audits["full"]["base"]
    full_benchmark = audits["full"]["buy_and_hold"]
    last_base = audits["last_120d"]["base"]
    last_benchmark = audits["last_120d"]["buy_and_hold"]
    observation_alias = (
        ALIAS
        if variant == VARIANT_BASELINE
        else f"{ALIAS}-V2-OBS"
    )
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": FAMILY,
        "alias": observation_alias,
        "variant": variant,
        "status": "explore / not promoted / not live-ready",
        "contract": {
            "ma": "SMA7",
            "rsi": "TradingView/Wilder RSI6 with SMA seed",
            "flat_to_long": "close > SMA7",
            "long_to_short": (
                "close < SMA7 and any of current/previous two RSI6 > 70"
            ),
            "short_to_flat": "RSI6 < 30",
            "short_to_long": (
                "disabled"
                if variant == VARIANT_BASELINE
                else "close > SMA7, evaluated before RSI6 < 30"
            ),
            "execution": "closed 4h signal; next 4h open",
            "fee_per_fill": FEE,
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "funding": "actual Binance event timestamp/rate",
            "parameter_search": False,
        },
        "backtest_engine": {
            "path": str(BACKTEST_ENGINE.relative_to(ROOT)),
            "sha256": BACKTEST_ENGINE_SHA256,
        },
        "data_quality": {
            str(phase): item.quality
            for phase, item in bundles.items()
        },
        "audits": audits,
        "trade_components": components,
        "phase_audit": phases,
        "rolling_90d": rolling,
        "recent_slices": recent,
        "decision": {
            "full_positive": full_base["equity_multiple"] > 1.0,
            "last_120d_positive": last_base["equity_multiple"] > 1.0,
            "full_excess_return_pct": (
                full_base["net_return_pct"]
                - full_benchmark["net_return_pct"]
            ),
            "last_120d_excess_return_pct": (
                last_base["net_return_pct"]
                - last_benchmark["net_return_pct"]
            ),
            "stress_positive": audits["full"]["stress_8bps"][
                "equity_multiple"
            ]
            > 1.0,
            "delay_positive": audits["full"]["delay_1bar"][
                "equity_multiple"
            ]
            > 1.0,
            "all_phases_positive": all(
                row["equity_multiple"] > 1.0 for row in phases
            ),
            "protection_blocker": "no hard stop or exchange-resident protection",
            "registration_effect": "none",
            "promotion_effect": "none",
        },
        "warning": (
            "All history is researcher-exposed. This fixed-parameter result "
            "is diagnostic evidence, not prospective OOS."
        ),
    }
    indicator_frame = pd.DataFrame(
        {
            "ts": bundle.bars["ts"],
            "close": bundle.bars["close"],
            "sma7": full_strategy["sma7"],
            "rsi6": full_strategy["rsi6"],
            "rsi6_max_last3": full_strategy["rsi_max3"],
            "target_after_close": full_strategy["targets"],
            "transition": full_strategy["transitions"],
        }
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = (
        "hype_4h_ma7_rsi6_asymmetric_reversal"
        if variant == VARIANT_BASELINE
        else "hype_4h_ma7_rsi6_v2_cross_reentry"
    )
    summary_path = ARTIFACT_DIR / f"{stem}_summary_{run_date}.json"
    summary_path.write_text(
        json.dumps(
            engine.clean_json(payload),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(phases).to_csv(
        ARTIFACT_DIR / f"{stem}_phase_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_90d_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(recent).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(components).to_csv(
        ARTIFACT_DIR / f"{stem}_trade_components_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(full_result.trades).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(full_result.path).to_csv(
        ARTIFACT_DIR / f"{stem}_path_{run_date}.csv",
        index=False,
    )
    indicator_frame.to_csv(
        ARTIFACT_DIR / f"{stem}_indicators_{run_date}.csv",
        index=False,
    )
    print(
        json.dumps(
            engine.clean_json(
                {
                    "summary": str(summary_path.relative_to(ROOT)),
                    "full": audits["full"],
                    "last_120d": audits["last_120d"],
                    "trade_components": components,
                    "phase_audit": phases,
                    "decision": payload["decision"],
                }
            ),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        flush=True,
    )


def self_test() -> None:
    up = wilder_rsi(np.arange(1.0, 9.0))
    down = wilder_rsi(np.arange(9.0, 1.0, -1.0))
    flat = wilder_rsi(np.ones(8))
    assert up[RSI_WINDOW] == 100.0
    assert down[RSI_WINDOW] == 0.0
    assert flat[RSI_WINDOW] == 50.0
    close = np.asarray([11.0, 12.0, 9.0, 8.0, 12.0])
    sma = np.asarray([10.0, 10.0, 10.0, 10.0, 10.0])
    rsi = np.asarray([60.0, 71.0, 65.0, 29.0, 45.0])
    targets, transitions = strategy_targets_from_arrays(close, sma, rsi)
    assert targets.tolist() == [1, 1, -1, 0, 1]
    assert transitions == [
        "flat_to_long",
        "hold",
        "long_to_short",
        "short_to_flat",
        "flat_to_long",
    ]
    v2_close = np.asarray([11.0, 9.0, 11.0])
    v2_sma = np.asarray([10.0, 10.0, 10.0])
    v2_rsi = np.asarray([71.0, 65.0, 25.0])
    v2_targets, v2_transitions = strategy_targets_from_arrays(
        v2_close,
        v2_sma,
        v2_rsi,
        short_cross_reentry=True,
    )
    assert v2_targets.tolist() == [1, -1, 1]
    assert v2_transitions == [
        "flat_to_long",
        "long_to_short",
        "short_to_long",
    ]
    print("self-test: PASS")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    engine = load_module(
        BACKTEST_ENGINE,
        BACKTEST_ENGINE_SHA256,
        "hype_4h_ma7_rsi6_backtest",
    )
    adapter = engine.load_module(
        engine.SOURCE_ADAPTER,
        engine.SOURCE_ADAPTER_SHA256,
        "hype_4h_ma7_rsi6_adapter",
    )
    base = adapter.load_module(
        adapter.BASE_PATH,
        adapter.BASE_SHA256,
        "hype_4h_ma7_rsi6_base",
    )
    parent_digest = hashlib.sha256(base.PARENT_SCRIPT.read_bytes()).hexdigest()
    if parent_digest != engine.PARENT_LOADER_SHA256:
        raise RuntimeError(
            "parent data loader drift: "
            f"expected {engine.PARENT_LOADER_SHA256}, got {parent_digest}"
        )
    parent = base.load_parent()
    data_engine = parent.load_engine()
    hourly, hourly_quality = data_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = data_engine.load_and_audit_funding(ROOT)
    bundles = {
        phase: engine.build_bundle(
            adapter,
            hourly,
            hourly_quality,
            funding,
            funding_quality,
            phase_hours=phase,
        )
        for phase in PHASES
    }
    write_outputs(
        engine=engine,
        bundles=bundles,
        run_date=args.run_date,
        variant=args.variant,
    )


if __name__ == "__main__":
    main()
