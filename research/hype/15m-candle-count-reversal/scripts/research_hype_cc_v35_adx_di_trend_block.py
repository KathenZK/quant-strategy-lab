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
BASE_SCRIPT = FAMILY_DIR / "scripts/research_hype_cc_v35_dual_ema_filter.py"
SELECTION_END = pd.Timestamp("2026-06-01T03:00:00Z")
HOLDOUT_START = SELECTION_END + pd.Timedelta(minutes=15)
ADX_WINDOWS = (14, 28, 56, 96)
ADX_THRESHOLDS = (20.0, 25.0, 30.0, 35.0, 40.0)
SUMMARY_PATH = ARTIFACT_DIR / "hype_cc_v35_adx_di_summary_2026-07-14.json"
GRID_PATH = ARTIFACT_DIR / "hype_cc_v35_adx_di_grid_2026-07-14.csv"
ROLLING_PATH = ARTIFACT_DIR / "hype_cc_v35_adx_di_rolling_2026-07-14.csv"
RECENT_PATH = ARTIFACT_DIR / "hype_cc_v35_adx_di_recent_2026-07-14.csv"
TRADES_PATH = ARTIFACT_DIR / "hype_cc_v35_adx_di_selected_trades_2026-07-14.csv"


def load_base_module():
    spec = importlib.util.spec_from_file_location("hype_cc_v35_dual_ema_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base research module: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["hype_cc_v35_dual_ema_base"] = module
    spec.loader.exec_module(module)
    return module


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def adx_di(
    frame: pd.DataFrame,
    window: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    up_move = frame["high"].diff()
    down_move = -frame["low"].diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0),
        index=frame.index,
        dtype="float64",
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0),
        index=frame.index,
        dtype="float64",
    )
    alpha = 1.0 / window
    atr = true_range(frame).ewm(
        alpha=alpha,
        adjust=False,
        min_periods=window,
    ).mean()
    plus_di = (
        100.0
        * plus_dm.ewm(alpha=alpha, adjust=False, min_periods=window).mean()
        / atr.replace(0.0, np.nan)
    )
    minus_di = (
        100.0
        * minus_dm.ewm(alpha=alpha, adjust=False, min_periods=window).mean()
        / atr.replace(0.0, np.nan)
    )
    dx = (
        100.0
        * (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(0.0, np.nan)
    )
    adx = dx.ewm(alpha=alpha, adjust=False, min_periods=window).mean()
    return adx, plus_di, minus_di


def make_direction_filter(
    adx: pd.Series,
    plus_di: pd.Series,
    minus_di: pd.Series,
    threshold: float,
) -> Callable[[int, int], bool]:
    def allows(position: int, direction: int) -> bool:
        adx_value = float(adx.iloc[position])
        plus_value = float(plus_di.iloc[position])
        minus_value = float(minus_di.iloc[position])
        if not all(np.isfinite(value) for value in (adx_value, plus_value, minus_value)):
            return False
        if adx_value < threshold:
            return True
        if plus_value > minus_value:
            return direction > 0
        if minus_value > plus_value:
            return direction < 0
        return False

    return allows


def run_candidate(
    base,
    replay,
    frame: pd.DataFrame,
    config,
    *,
    indicators: dict[int, tuple[pd.Series, pd.Series, pd.Series]],
    adx_window: int | None,
    adx_threshold: float | None,
    trade_start: pd.Timestamp | str | None = None,
    trade_end: pd.Timestamp | str | None = None,
):
    direction_filter = None
    if adx_window is not None and adx_threshold is not None:
        adx, plus_di, minus_di = indicators[adx_window]
        direction_filter = make_direction_filter(
            adx,
            plus_di,
            minus_di,
            adx_threshold,
        )
    return base.run_next_open(
        replay,
        frame,
        config,
        direction_filter=direction_filter,
        trade_start=trade_start,
        trade_end=trade_end,
    )


def aggregate_rolling(rows: pd.DataFrame) -> pd.DataFrame:
    result: list[dict[str, Any]] = []
    for candidate, group in rows.groupby("candidate", sort=False):
        result.append(
            {
                "candidate": candidate,
                "adx_window": group["adx_window"].iloc[0],
                "adx_threshold": group["adx_threshold"].iloc[0],
                "positive_window_rate": float((group["return_pct"] > 0.0).mean()),
                "median_return_pct": float(group["return_pct"].median()),
                "median_sharpe": float(group["sharpe"].median()),
                "median_max_drawdown_pct": float(
                    group["max_drawdown_pct"].median()
                ),
                "worst_max_drawdown_pct": float(group["max_drawdown_pct"].min()),
                "median_entries": float(group["entries"].median()),
                "total_entries": int(group["entries"].sum()),
                "zero_trade_windows": int((group["entries"] == 0).sum()),
                "window_count": int(len(group)),
            }
        )
    return pd.DataFrame(result)


def is_neighbor(
    window_a: int,
    threshold_a: float,
    window_b: int,
    threshold_b: float,
) -> bool:
    window_distance = abs(ADX_WINDOWS.index(window_a) - ADX_WINDOWS.index(window_b))
    threshold_distance = abs(
        ADX_THRESHOLDS.index(threshold_a) - ADX_THRESHOLDS.index(threshold_b)
    )
    return window_distance + threshold_distance == 1


def json_record(row: pd.Series) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.to_dict().items():
        if isinstance(value, (np.integer,)):
            result[key] = int(value)
        elif isinstance(value, (np.floating,)):
            result[key] = None if np.isnan(value) else float(value)
        else:
            result[key] = value
    return result


def main() -> None:
    base = load_base_module()
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

    indicators = {
        window: adx_di(frame, window)
        for window in ADX_WINDOWS
    }
    rolling_windows = base.build_oos_windows(frame.index[0], SELECTION_END)
    candidates: list[tuple[int | None, float | None]] = [
        (None, None),
        *[
            (window, threshold)
            for window in ADX_WINDOWS
            for threshold in ADX_THRESHOLDS
        ],
    ]
    rolling_rows: list[dict[str, Any]] = []
    for adx_window, adx_threshold in candidates:
        candidate_name = (
            "V35 baseline"
            if adx_window is None
            else f"ADX{adx_window}>={adx_threshold:g}"
        )
        for window_name, start, end in rolling_windows:
            run = run_candidate(
                base,
                replay,
                frame,
                config,
                indicators=indicators,
                adx_window=adx_window,
                adx_threshold=adx_threshold,
                trade_start=start,
                trade_end=end,
            )
            rolling_rows.append(
                {
                    "candidate": candidate_name,
                    "adx_window": adx_window,
                    "adx_threshold": adx_threshold,
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
        (grid["positive_window_rate"] >= 0.60)
        & (grid["median_sharpe"] > float(baseline["median_sharpe"]))
        & (
            grid["median_return_pct"]
            >= 0.80 * float(baseline["median_return_pct"])
        )
        & (
            grid["worst_max_drawdown_pct"]
            >= float(baseline["worst_max_drawdown_pct"])
        )
        & (grid["trade_retention"] >= 0.50)
    )
    grid = grid.sort_values(
        ["pre_pass", "median_sharpe", "median_return_pct"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    selected = grid.iloc[0]
    selected_window = int(selected["adx_window"])
    selected_threshold = float(selected["adx_threshold"])

    robust_neighbors = grid.loc[
        grid.apply(
            lambda row: is_neighbor(
                selected_window,
                selected_threshold,
                int(row["adx_window"]),
                float(row["adx_threshold"]),
            ),
            axis=1,
        )
        & (
            grid["positive_window_rate"]
            >= float(baseline["positive_window_rate"])
        )
        & (
            grid["median_return_pct"]
            >= 0.80 * float(baseline["median_return_pct"])
        )
        & (grid["median_sharpe"] >= float(baseline["median_sharpe"]))
        & (
            grid["worst_max_drawdown_pct"]
            >= float(baseline["worst_max_drawdown_pct"])
        )
    ]
    plateau_pass = len(robust_neighbors) >= 2

    holdout_end = frame.index[-1]
    holdout_baseline = run_candidate(
        base,
        replay,
        frame,
        config,
        indicators=indicators,
        adx_window=None,
        adx_threshold=None,
        trade_start=HOLDOUT_START,
        trade_end=holdout_end,
    )
    holdout_selected = run_candidate(
        base,
        replay,
        frame,
        config,
        indicators=indicators,
        adx_window=selected_window,
        adx_threshold=selected_threshold,
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
        >= 0.50 * holdout_baseline_metrics["entries"]
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
    for window_name, delta in recent_windows.items():
        start = max(frame.index[0], holdout_end - delta)
        for candidate_name, adx_window, adx_threshold in (
            ("V35 baseline", None, None),
            (
                f"ADX{selected_window}>={selected_threshold:g}",
                selected_window,
                selected_threshold,
            ),
        ):
            run = run_candidate(
                base,
                replay,
                frame,
                config,
                indicators=indicators,
                adx_window=adx_window,
                adx_threshold=adx_threshold,
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

    full_baseline = run_candidate(
        base,
        replay,
        frame,
        config,
        indicators=indicators,
        adx_window=None,
        adx_threshold=None,
    )
    full_selected = run_candidate(
        base,
        replay,
        frame,
        config,
        indicators=indicators,
        adx_window=selected_window,
        adx_threshold=selected_threshold,
    )
    stress_config = replace(config, fee_rate=0.001, slippage_rate=0.0004)
    stress_baseline = run_candidate(
        base,
        replay,
        frame,
        stress_config,
        indicators=indicators,
        adx_window=None,
        adx_threshold=None,
    )
    stress_selected = run_candidate(
        base,
        replay,
        frame,
        stress_config,
        indicators=indicators,
        adx_window=selected_window,
        adx_threshold=selected_threshold,
    )
    final_pass = bool(selected["pre_pass"]) and plateau_pass and holdout_pass

    selected_trades = full_selected.trades.copy()
    if not selected_trades.empty:
        selected_trades.insert(
            0,
            "candidate",
            f"ADX{selected_window}>={selected_threshold:g}",
        )
    grid["robust_neighbor_of_selected"] = grid.apply(
        lambda row: is_neighbor(
            selected_window,
            selected_threshold,
            int(row["adx_window"]),
            float(row["adx_threshold"]),
        ),
        axis=1,
    )
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": "HYPE-Candle-Count-Reversal-V35 + ADX/DI strong-trend block",
        "status": (
            "candidate passed; eligible for V36 registration"
            if final_pass
            else "candidate failed; do not register V36"
        ),
        "data_quality": quality,
        "indicator_contract": {
            "source": "closed 15m high/low/close",
            "formula": "Wilder-style EWM; alpha=1/window, adjust=False",
            "windows": list(ADX_WINDOWS),
            "thresholds": list(ADX_THRESHOLDS),
            "rule": (
                "ADX below threshold allows both sides; at/above threshold, "
                "+DI>-DI permits long only and -DI>+DI permits short only"
            ),
            "not_ready_or_di_tie": "block entry",
            "existing_96_bar_5pct_trend_filter": "retained",
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
        "baseline_parity": {
            "expected": base.CURRENT_BASELINE,
            "actual": canonical_metrics,
            "checks": parity,
        },
        "selection": {
            "selection_data_end": SELECTION_END.isoformat(),
            "holdout_start": HOLDOUT_START.isoformat(),
            "holdout_end": holdout_end.isoformat(),
            "rolling_contract": (
                "pre-holdout 30d evaluation windows, starting after 70d history "
                "and stepped by 30d"
            ),
            "rolling_window_count": len(rolling_windows),
            "selected_adx_window": selected_window,
            "selected_adx_threshold": selected_threshold,
            "selected_pre_holdout": json_record(selected),
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
