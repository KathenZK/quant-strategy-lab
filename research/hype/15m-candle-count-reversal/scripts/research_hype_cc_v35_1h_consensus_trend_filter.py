from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-candle-count-reversal"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ADX_SCRIPT = FAMILY_DIR / "scripts/research_hype_cc_v35_adx_di_trend_block.py"
SELECTION_END = pd.Timestamp("2026-06-01T03:00:00Z")
HOLDOUT_START = SELECTION_END + pd.Timedelta(minutes=15)
EMA_PAIRS = ((24, 72), (24, 96))
ADX_ENTRY_THRESHOLDS = (20.0, 25.0, 30.0)
ADX_WINDOW = 14
ADX_EXIT_GAP = 5.0
SLOPE_BARS = 3
SUMMARY_PATH = (
    ARTIFACT_DIR / "hype_cc_v35_1h_consensus_trend_summary_2026-07-15.json"
)
GRID_PATH = ARTIFACT_DIR / "hype_cc_v35_1h_consensus_trend_grid_2026-07-15.csv"
ROLLING_PATH = (
    ARTIFACT_DIR / "hype_cc_v35_1h_consensus_trend_rolling_2026-07-15.csv"
)
RECENT_PATH = (
    ARTIFACT_DIR / "hype_cc_v35_1h_consensus_trend_recent_2026-07-15.csv"
)
TRADES_PATH = (
    ARTIFACT_DIR
    / "hype_cc_v35_1h_consensus_trend_selected_trades_2026-07-15.csv"
)


def load_adx_module():
    spec = importlib.util.spec_from_file_location("hype_cc_v35_adx_for_htf", ADX_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load ADX research module: {ADX_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["hype_cc_v35_adx_for_htf"] = module
    spec.loader.exec_module(module)
    return module


def build_closed_hourly(frame: pd.DataFrame) -> pd.DataFrame:
    source = frame[["open", "high", "low", "close", "volume"]]
    grouped = source.resample("1h", label="left", closed="left")
    hourly = grouped.agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    counts = grouped["close"].count()
    hourly = hourly.loc[counts.eq(4)].dropna()
    hourly.index = pd.DatetimeIndex(hourly.index, tz="UTC")
    return hourly


def build_regime(
    adx_module,
    frame: pd.DataFrame,
    *,
    fast_span: int,
    slow_span: int,
    adx_entry: float,
) -> tuple[pd.Series, dict[str, Any]]:
    hourly = build_closed_hourly(frame)
    fast = hourly["close"].ewm(
        span=fast_span,
        adjust=False,
        min_periods=fast_span,
    ).mean()
    slow = hourly["close"].ewm(
        span=slow_span,
        adjust=False,
        min_periods=slow_span,
    ).mean()
    adx, plus_di, minus_di = adx_module.adx_di(hourly, ADX_WINDOW)
    up_slope = fast.diff().gt(0.0).rolling(
        SLOPE_BARS,
        min_periods=SLOPE_BARS,
    ).sum().eq(float(SLOPE_BARS))
    down_slope = fast.diff().lt(0.0).rolling(
        SLOPE_BARS,
        min_periods=SLOPE_BARS,
    ).sum().eq(float(SLOPE_BARS))
    raw_up = fast.gt(slow) & up_slope & plus_di.gt(minus_di)
    raw_down = fast.lt(slow) & down_slope & minus_di.gt(plus_di)
    adx_exit = adx_entry - ADX_EXIT_GAP

    hourly_state = pd.Series(0, index=hourly.index, dtype="int8")
    state = 0
    for position in range(len(hourly)):
        adx_value = float(adx.iloc[position])
        if not np.isfinite(adx_value):
            state = 0
        elif bool(raw_up.iloc[position]):
            required = adx_exit if state == 1 else adx_entry
            state = 1 if adx_value >= required else 0
        elif bool(raw_down.iloc[position]):
            required = adx_exit if state == -1 else adx_entry
            state = -1 if adx_value >= required else 0
        else:
            state = 0
        hourly_state.iloc[position] = state

    available_state = hourly_state.copy()
    available_state.index = available_state.index + pd.Timedelta(hours=1)
    signal_close_times = pd.DatetimeIndex(frame.index) + pd.Timedelta(minutes=15)
    projected = available_state.reindex(signal_close_times, method="ffill").fillna(0)
    projected.index = frame.index
    projected = projected.astype("int8")
    metadata = {
        "hourly_rows": int(len(hourly)),
        "hourly_start": hourly.index[0].isoformat(),
        "hourly_end": hourly.index[-1].isoformat(),
        "first_feature_available": (
            available_state.loc[available_state.ne(0)].index[0].isoformat()
            if available_state.ne(0).any()
            else None
        ),
        "hourly_up_regime_bars": int(hourly_state.eq(1).sum()),
        "hourly_down_regime_bars": int(hourly_state.eq(-1).sum()),
        "hourly_neutral_bars": int(hourly_state.eq(0).sum()),
        "projected_up_15m_bars": int(projected.eq(1).sum()),
        "projected_down_15m_bars": int(projected.eq(-1).sum()),
        "projected_neutral_15m_bars": int(projected.eq(0).sum()),
    }
    return projected, metadata


def make_direction_filter(regime: pd.Series) -> Callable[[int, int], bool]:
    def allows(position: int, direction: int) -> bool:
        state = int(regime.iloc[position])
        if state > 0:
            return direction > 0
        if state < 0:
            return direction < 0
        return True

    return allows


def run_variant(
    base,
    replay,
    frame: pd.DataFrame,
    config,
    *,
    regime: pd.Series | None,
    trade_start: pd.Timestamp | str | None = None,
    trade_end: pd.Timestamp | str | None = None,
):
    return base.run_next_open(
        replay,
        frame,
        config,
        direction_filter=(
            make_direction_filter(regime) if regime is not None else None
        ),
        apply_original_trend_filter=True,
        trade_start=trade_start,
        trade_end=trade_end,
    )


def aggregate_rolling(rows: pd.DataFrame) -> pd.DataFrame:
    result: list[dict[str, Any]] = []
    for candidate, group in rows.groupby("candidate", sort=False):
        result.append(
            {
                "candidate": candidate,
                "ema_fast": group["ema_fast"].iloc[0],
                "ema_slow": group["ema_slow"].iloc[0],
                "adx_entry": group["adx_entry"].iloc[0],
                "adx_exit": group["adx_exit"].iloc[0],
                "positive_window_rate": float((group["return_pct"] > 0.0).mean()),
                "median_return_pct": float(group["return_pct"].median()),
                "median_sharpe": float(group["sharpe"].median()),
                "median_max_drawdown_pct": float(
                    group["max_drawdown_pct"].median()
                ),
                "worst_max_drawdown_pct": float(group["max_drawdown_pct"].min()),
                "median_entries": float(group["entries"].median()),
                "total_entries": int(group["entries"].sum()),
                "total_blocked": int(
                    group["blocked_by_direction_filter"].sum()
                ),
                "zero_trade_windows": int((group["entries"] == 0).sum()),
                "window_count": int(len(group)),
            }
        )
    return pd.DataFrame(result)


def is_neighbor(
    pair_a: tuple[int, int],
    threshold_a: float,
    pair_b: tuple[int, int],
    threshold_b: float,
) -> bool:
    pair_distance = abs(EMA_PAIRS.index(pair_a) - EMA_PAIRS.index(pair_b))
    threshold_distance = abs(
        ADX_ENTRY_THRESHOLDS.index(threshold_a)
        - ADX_ENTRY_THRESHOLDS.index(threshold_b)
    )
    return pair_distance + threshold_distance == 1


def json_record(row: pd.Series) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.to_dict().items():
        if pd.isna(value):
            result[key] = None
        elif isinstance(value, np.integer):
            result[key] = int(value)
        elif isinstance(value, np.floating):
            result[key] = float(value)
        else:
            result[key] = value
    return result


def main() -> None:
    adx_module = load_adx_module()
    base = adx_module.load_base_module()
    replay = base._load_replay_module()
    frame, quality = base.load_and_audit_frame()
    config = replay.hype_v35_config()
    if frame.index[-1] < HOLDOUT_START:
        raise RuntimeError("post-selection holdout data is unavailable")

    selection_frame = frame.loc[frame.index <= SELECTION_END]
    canonical_baseline = base.run_canonical(replay, selection_frame, config)
    canonical_metrics = base.compact_metrics(canonical_baseline)
    parity = {
        key: (
            int(canonical_metrics[key]) == int(expected)
            if key == "entries"
            else abs(float(canonical_metrics[key]) - float(expected)) < 0.02
        )
        for key, expected in base.CURRENT_BASELINE.items()
    }
    if not all(parity.values()):
        raise RuntimeError(
            "V35 baseline parity failed: "
            f"actual={canonical_metrics}, expected={base.CURRENT_BASELINE}"
        )

    regimes: dict[tuple[int, int, float], pd.Series] = {}
    regime_metadata: dict[str, dict[str, Any]] = {}
    for fast_span, slow_span in EMA_PAIRS:
        for adx_entry in ADX_ENTRY_THRESHOLDS:
            regime, metadata = build_regime(
                adx_module,
                frame,
                fast_span=fast_span,
                slow_span=slow_span,
                adx_entry=adx_entry,
            )
            regimes[(fast_span, slow_span, adx_entry)] = regime
            regime_metadata[
                f"EMA{fast_span}/{slow_span}_ADX{adx_entry:g}/{adx_entry - ADX_EXIT_GAP:g}"
            ] = metadata

    rolling_windows = base.build_oos_windows(frame.index[0], SELECTION_END)
    candidates: list[tuple[int | None, int | None, float | None]] = [
        (None, None, None),
        *[
            (fast_span, slow_span, adx_entry)
            for fast_span, slow_span in EMA_PAIRS
            for adx_entry in ADX_ENTRY_THRESHOLDS
        ],
    ]
    rolling_rows: list[dict[str, Any]] = []
    for fast_span, slow_span, adx_entry in candidates:
        candidate_name = (
            "V35 baseline"
            if fast_span is None
            else (
                f"1h EMA{fast_span}/{slow_span} "
                f"ADX{adx_entry:g}/{adx_entry - ADX_EXIT_GAP:g}"
            )
        )
        regime = (
            None
            if fast_span is None or slow_span is None or adx_entry is None
            else regimes[(fast_span, slow_span, adx_entry)]
        )
        for window_name, start, end in rolling_windows:
            run = run_variant(
                base,
                replay,
                frame,
                config,
                regime=regime,
                trade_start=start,
                trade_end=end,
            )
            rolling_rows.append(
                {
                    "candidate": candidate_name,
                    "ema_fast": fast_span,
                    "ema_slow": slow_span,
                    "adx_entry": adx_entry,
                    "adx_exit": (
                        None if adx_entry is None else adx_entry - ADX_EXIT_GAP
                    ),
                    "window": window_name,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    **base.compact_metrics(run),
                }
            )
    rolling = pd.DataFrame(rolling_rows)
    aggregate = aggregate_rolling(rolling)
    baseline = aggregate.loc[aggregate["candidate"].eq("V35 baseline")].iloc[0]
    grid = aggregate.loc[~aggregate["candidate"].eq("V35 baseline")].copy()
    grid["trade_retention"] = (
        grid["median_entries"] / float(baseline["median_entries"])
    )
    grid["pre_pass"] = (
        (grid["median_return_pct"] >= 0.80 * float(baseline["median_return_pct"]))
        & (grid["median_sharpe"] >= float(baseline["median_sharpe"]))
        & (
            grid["worst_max_drawdown_pct"]
            >= float(baseline["worst_max_drawdown_pct"])
        )
        & (grid["trade_retention"] >= 0.70)
        & (grid["total_blocked"] > 0)
    )
    grid = grid.sort_values(
        ["pre_pass", "median_sharpe", "median_return_pct"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    selected = grid.iloc[0]
    selected_fast = int(selected["ema_fast"])
    selected_slow = int(selected["ema_slow"])
    selected_entry = float(selected["adx_entry"])
    selected_key = (selected_fast, selected_slow, selected_entry)

    robust_neighbors = grid.loc[
        grid.apply(
            lambda row: is_neighbor(
                (selected_fast, selected_slow),
                selected_entry,
                (int(row["ema_fast"]), int(row["ema_slow"])),
                float(row["adx_entry"]),
            ),
            axis=1,
        )
        & (
            grid["median_return_pct"]
            >= 0.80 * float(baseline["median_return_pct"])
        )
        & (grid["median_sharpe"] >= 0.90 * float(baseline["median_sharpe"]))
        & (
            grid["worst_max_drawdown_pct"]
            >= float(baseline["worst_max_drawdown_pct"])
        )
        & (grid["trade_retention"] >= 0.70)
    ]
    plateau_pass = len(robust_neighbors) >= 2

    holdout_end = frame.index[-1]
    holdout_baseline = run_variant(
        base,
        replay,
        frame,
        config,
        regime=None,
        trade_start=HOLDOUT_START,
        trade_end=holdout_end,
    )
    holdout_selected = run_variant(
        base,
        replay,
        frame,
        config,
        regime=regimes[selected_key],
        trade_start=HOLDOUT_START,
        trade_end=holdout_end,
    )
    holdout_baseline_metrics = base.compact_metrics(holdout_baseline)
    holdout_selected_metrics = base.compact_metrics(holdout_selected)
    holdout_pass = (
        holdout_selected_metrics["return_pct"]
        > holdout_baseline_metrics["return_pct"]
        and holdout_selected_metrics["max_drawdown_pct"]
        >= holdout_baseline_metrics["max_drawdown_pct"]
        and holdout_selected_metrics["entries"]
        >= 0.70 * holdout_baseline_metrics["entries"]
    )

    recent_windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    recent_rows: list[dict[str, Any]] = []
    selected_name = (
        f"1h EMA{selected_fast}/{selected_slow} "
        f"ADX{selected_entry:g}/{selected_entry - ADX_EXIT_GAP:g}"
    )
    for window_name, delta in recent_windows.items():
        start = max(frame.index[0], holdout_end - delta)
        for candidate_name, regime in (
            ("V35 baseline", None),
            (selected_name, regimes[selected_key]),
        ):
            run = run_variant(
                base,
                replay,
                frame,
                config,
                regime=regime,
                trade_start=start,
                trade_end=holdout_end,
            )
            recent_rows.append(
                {
                    "window": window_name,
                    "candidate": candidate_name,
                    "start": start.isoformat(),
                    "end": holdout_end.isoformat(),
                    "fee_rate": config.fee_rate,
                    "slippage_rate": config.slippage_rate,
                    **base.compact_metrics(run),
                }
            )

    full_baseline = run_variant(
        base,
        replay,
        frame,
        config,
        regime=None,
    )
    full_selected = run_variant(
        base,
        replay,
        frame,
        config,
        regime=regimes[selected_key],
    )
    stress_config = replace(config, fee_rate=0.001, slippage_rate=0.0004)
    stress_baseline = run_variant(
        base,
        replay,
        frame,
        stress_config,
        regime=None,
    )
    stress_selected = run_variant(
        base,
        replay,
        frame,
        stress_config,
        regime=regimes[selected_key],
    )
    final_pass = bool(selected["pre_pass"]) and plateau_pass and holdout_pass

    selected_trades = full_selected.trades.copy()
    if not selected_trades.empty:
        selected_trades.insert(0, "candidate", selected_name)
    grid["robust_neighbor_of_selected"] = grid.apply(
        lambda row: is_neighbor(
            (selected_fast, selected_slow),
            selected_entry,
            (int(row["ema_fast"]), int(row["ema_slow"])),
            float(row["adx_entry"]),
        ),
        axis=1,
    )
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": (
            "HYPE-Candle-Count-Reversal-V35 + closed-1h "
            "EMA/ADX/DI consensus trend block"
        ),
        "status": (
            "candidate passed; eligible for V36 registration"
            if final_pass
            else "candidate failed; do not register V36"
        ),
        "data_quality": quality,
        "filter_contract": {
            "original_96_bar_5pct_filter": "retained",
            "source_timeframe": "1h aggregated from complete groups of four 15m bars",
            "availability": (
                "1h features become available at bucket_start + 1h and are "
                "projected to 15m signal close; incomplete current hour excluded"
            ),
            "ema_pairs": [list(pair) for pair in EMA_PAIRS],
            "adx_window": ADX_WINDOW,
            "adx_entry_thresholds": list(ADX_ENTRY_THRESHOLDS),
            "adx_exit_gap": ADX_EXIT_GAP,
            "ema_slope_bars": SLOPE_BARS,
            "up_regime": (
                "EMAfast>EMAslow, EMAfast rises 3 consecutive 1h changes, "
                "ADX14 above hysteresis threshold, +DI14>-DI14"
            ),
            "down_regime": "symmetric inverse",
            "up_regime_action": "block short entries only",
            "down_regime_action": "block long entries only",
            "neutral_action": "allow both V35 directions",
        },
        "regime_metadata": regime_metadata,
        "baseline_parity": {
            "expected": base.CURRENT_BASELINE,
            "actual": canonical_metrics,
            "checks": parity,
        },
        "selection": {
            "selection_data_end": SELECTION_END.isoformat(),
            "holdout_start": HOLDOUT_START.isoformat(),
            "holdout_end": holdout_end.isoformat(),
            "rolling_window_count": len(rolling_windows),
            "selected": json_record(selected),
            "baseline_pre_holdout": json_record(baseline),
            "robust_neighbor_count": int(len(robust_neighbors)),
            "robust_neighbors": [
                json_record(row)
                for _, row in robust_neighbors.iterrows()
            ],
            "plateau_pass": plateau_pass,
            "holdout_baseline": holdout_baseline_metrics,
            "holdout_selected": holdout_selected_metrics,
            "holdout_pass": holdout_pass,
            "final_pass": final_pass,
        },
        "full_period": {
            "next_open_baseline": base.compact_metrics(full_baseline),
            "next_open_selected": base.compact_metrics(full_selected),
            "binance_cost_stress_baseline": base.compact_metrics(stress_baseline),
            "binance_cost_stress_selected": base.compact_metrics(stress_selected),
        },
        "execution": {
            "selection_mode": "signal confirmed on closed bar; next bar open entry",
            "same_entry_bar_stop_take": True,
            "fee_rate_primary": config.fee_rate,
            "slippage_rate_primary": config.slippage_rate,
            "fee_rate_stress": stress_config.fee_rate,
            "slippage_rate_stress": stress_config.slippage_rate,
            "funding": "Binance funding history included",
            "stop_take_trigger": (
                "Binance 15m mark-price high/low; stop first on conflict"
            ),
        },
        "artifacts": {
            "grid": str(GRID_PATH.relative_to(ROOT)),
            "rolling": str(ROLLING_PATH.relative_to(ROOT)),
            "recent": str(RECENT_PATH.relative_to(ROOT)),
            "selected_trades": str(TRADES_PATH.relative_to(ROOT)),
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    grid.to_csv(GRID_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    pd.DataFrame(recent_rows).to_csv(RECENT_PATH, index=False)
    selected_trades.to_csv(TRADES_PATH, index=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Wrote {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
