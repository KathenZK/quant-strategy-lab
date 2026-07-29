from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import sds_engine as engine
from research_hype_15m_sds_regression_search import regression_features


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SUMMARY_PATH = ARTIFACT_DIR / "hype_15m_sds_breakout_retest_prefit_search.json"
RANKING_PATH = ARTIFACT_DIR / "hype_15m_sds_breakout_retest_prefit_ranking.csv"
TRADES_PATH = ARTIFACT_DIR / "hype_15m_sds_breakout_retest_prefit_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / "hype_15m_sds_breakout_retest_prefit_equity.csv"


def breakout_retest_states(
    book: engine.FeatureBook,
    regression: tuple[np.ndarray, np.ndarray, np.ndarray],
    *,
    breakout_window: int,
    exit_window: int,
    slope_t_entry: float,
    efficiency_min: float,
    retest_atr: float,
    arm_timeout_bars: int,
    exit_confirm_bars: int,
) -> engine.StateBook:
    slope_t, efficiency, _ = regression
    prior_high = (
        pd.Series(book.high)
        .shift(1)
        .rolling(breakout_window, min_periods=breakout_window)
        .max()
        .to_numpy("float64")
    )
    prior_low = (
        pd.Series(book.low)
        .shift(1)
        .rolling(breakout_window, min_periods=breakout_window)
        .min()
        .to_numpy("float64")
    )
    exit_high = (
        pd.Series(book.high)
        .shift(1)
        .rolling(exit_window, min_periods=exit_window)
        .max()
        .to_numpy("float64")
    )
    exit_low = (
        pd.Series(book.low)
        .shift(1)
        .rolling(exit_window, min_periods=exit_window)
        .min()
        .to_numpy("float64")
    )
    rows = book.rows
    desired = np.zeros(rows, dtype="int8")
    reasons = ["warmup"] * rows
    armed_direction = 0
    armed_level = math.nan
    armed_age = 0
    active_state = 0
    weak_count = 0

    for index in range(rows):
        ready = (
            np.isfinite(slope_t[index])
            and np.isfinite(efficiency[index])
            and np.isfinite(prior_high[index])
            and np.isfinite(prior_low[index])
            and np.isfinite(exit_high[index])
            and np.isfinite(exit_low[index])
            and np.isfinite(book.atr[index])
            and book.atr[index] > 0.0
        )
        if not ready:
            desired[index] = active_state
            continue

        long_trend = (
            slope_t[index] >= slope_t_entry
            and efficiency[index] >= efficiency_min
        )
        short_trend = (
            slope_t[index] <= -slope_t_entry
            and efficiency[index] >= efficiency_min
        )
        reason = "hold"

        if active_state == 0:
            if armed_direction:
                armed_age += 1
                trend_valid = long_trend if armed_direction == 1 else short_trend
                if not trend_valid or armed_age > arm_timeout_bars:
                    armed_direction = 0
                    armed_level = math.nan
                    armed_age = 0
                    reason = "arm_cancel"
                elif armed_direction == 1:
                    retested = book.low[index] <= (
                        armed_level + retest_atr * book.atr[index]
                    )
                    reclaimed = (
                        book.close[index] > armed_level
                        and book.close[index] > book.open[index]
                    )
                    if retested and reclaimed:
                        active_state = 1
                        armed_direction = 0
                        armed_level = math.nan
                        armed_age = 0
                        weak_count = 0
                        reason = "long_retest_start"
                else:
                    retested = book.high[index] >= (
                        armed_level - retest_atr * book.atr[index]
                    )
                    reclaimed = (
                        book.close[index] < armed_level
                        and book.close[index] < book.open[index]
                    )
                    if retested and reclaimed:
                        active_state = -1
                        armed_direction = 0
                        armed_level = math.nan
                        armed_age = 0
                        weak_count = 0
                        reason = "short_retest_start"

            if active_state == 0 and armed_direction == 0:
                if long_trend and book.close[index] > prior_high[index]:
                    armed_direction = 1
                    armed_level = float(prior_high[index])
                    armed_age = 0
                    reason = "long_arm"
                elif short_trend and book.close[index] < prior_low[index]:
                    armed_direction = -1
                    armed_level = float(prior_low[index])
                    armed_age = 0
                    reason = "short_arm"
        elif active_state == 1:
            weak = slope_t[index] <= 0.0
            weak_count = weak_count + 1 if weak else 0
            if (
                book.close[index] < exit_low[index]
                or weak_count >= exit_confirm_bars
            ):
                active_state = 0
                weak_count = 0
                reason = "long_end"
        else:
            weak = slope_t[index] >= 0.0
            weak_count = weak_count + 1 if weak else 0
            if (
                book.close[index] > exit_high[index]
                or weak_count >= exit_confirm_bars
            ):
                active_state = 0
                weak_count = 0
                reason = "short_end"

        desired[index] = active_state
        reasons[index] = reason

    zeros = np.zeros(rows, dtype="float64")
    return engine.StateBook(
        desired_state=desired,
        normalized_return=zeros.copy(),
        fast_drift=slope_t.copy(),
        slow_drift=zeros.copy(),
        efficiency_ratio=efficiency,
        positive_cusum=zeros.copy(),
        negative_cusum=zeros.copy(),
        transition_reason=reasons,
    )


def main() -> None:
    manifest = json.loads(engine.FREEZE_PATH.read_text(encoding="utf-8"))
    book = engine.build_book(include_locked_oos=False)
    if book.terminal_ts != pd.Timestamp(
        manifest["freeze_contract"]["locked_oos_start_inclusive"]
    ):
        raise RuntimeError("search book is not limited to the frozen prefit boundary")
    validation_start = book.terminal_ts - pd.DateOffset(months=3)
    regression_windows = (48, 96)
    regression_books = {
        window: regression_features(book, window)
        for window in regression_windows
    }
    backtest_config = engine.Config(stop_atr=4.0, max_hold_bars=384, leverage=1.0)
    rows: list[dict[str, object]] = []
    grid = itertools.product(
        regression_windows,
        (32, 64, 96),
        (16, 32),
        (1.5, 2.5),
        (0.20, 0.30),
        (0.25, 0.50),
        (8, 16),
        (2, 4),
    )
    for (
        regression_window,
        breakout_window,
        exit_window,
        slope_t_entry,
        efficiency_min,
        retest_atr,
        arm_timeout_bars,
        exit_confirm_bars,
    ) in grid:
        states = breakout_retest_states(
            book,
            regression_books[regression_window],
            breakout_window=breakout_window,
            exit_window=exit_window,
            slope_t_entry=slope_t_entry,
            efficiency_min=efficiency_min,
            retest_atr=retest_atr,
            arm_timeout_bars=arm_timeout_bars,
            exit_confirm_bars=exit_confirm_bars,
        )
        result = engine.run_backtest(book, backtest_config, states=states)
        train = engine.slice_metrics(
            result,
            start=book.source_start,
            end=validation_start,
        )
        validation = engine.slice_metrics(
            result,
            start=validation_start,
            end=book.terminal_ts,
        )
        valid_sample = train["trades"] >= 30 and validation["trades"] >= 10
        joint_positive = train["return"] > 0.0 and validation["return"] > 0.0
        score = (
            math.log(max(1e-9, 1.0 + train["return"]))
            + math.log(max(1e-9, 1.0 + validation["return"]))
            + 2.0 * result.metrics["max_drawdown"]
            if valid_sample
            else -1e9
        )
        rows.append(
            {
                "regression_window": regression_window,
                "breakout_window": breakout_window,
                "exit_window": exit_window,
                "slope_t_entry": slope_t_entry,
                "efficiency_min": efficiency_min,
                "retest_atr": retest_atr,
                "arm_timeout_bars": arm_timeout_bars,
                "exit_confirm_bars": exit_confirm_bars,
                "train_return": train["return"],
                "train_max_drawdown": train["max_drawdown"],
                "train_trades": train["trades"],
                "validation_return": validation["return"],
                "validation_max_drawdown": validation["max_drawdown"],
                "validation_trades": validation["trades"],
                "prefit_return": result.metrics["total_return"],
                "prefit_max_drawdown": result.metrics["max_drawdown"],
                "prefit_win_rate": result.metrics["win_rate"],
                "prefit_trades": result.metrics["trades"],
                "valid_sample": valid_sample,
                "joint_positive": joint_positive,
                "score": score,
            }
        )

    ranking = pd.DataFrame(rows)
    ranking["eligible"] = ranking["valid_sample"] & ranking["joint_positive"]
    ranking = ranking.sort_values(
        ["eligible", "valid_sample", "score"],
        ascending=[False, False, False],
    )
    selected = ranking.iloc[0].to_dict()
    selected_states = breakout_retest_states(
        book,
        regression_books[int(selected["regression_window"])],
        breakout_window=int(selected["breakout_window"]),
        exit_window=int(selected["exit_window"]),
        slope_t_entry=float(selected["slope_t_entry"]),
        efficiency_min=float(selected["efficiency_min"]),
        retest_atr=float(selected["retest_atr"]),
        arm_timeout_bars=int(selected["arm_timeout_bars"]),
        exit_confirm_bars=int(selected["exit_confirm_bars"]),
    )
    selected_result = engine.run_backtest(
        book,
        backtest_config,
        states=selected_states,
    )
    summary = {
        "family": "HYPE-15M-Sequential-Drift-State",
        "surface": "breakout-retest campaign",
        "status": "explore / prefit-only / not promoted / not live-ready",
        "locked_oos_loaded": False,
        "locked_oos_retested": False,
        "search_space_size": int(len(ranking)),
        "train_end_exclusive": validation_start.isoformat(),
        "validation_end_exclusive": book.terminal_ts.isoformat(),
        "valid_sample_count": int(ranking["valid_sample"].sum()),
        "eligible_count": int(ranking["eligible"].sum()),
        "selected_role": (
            "prefit prospective candidate"
            if bool(selected["eligible"])
            else "best valid-sample failure comparator"
        ),
        "selected": selected,
        "selected_metrics": selected_result.metrics,
        "decision": (
            "freeze selected prefit candidate without examining the already revealed "
            "window; only data after 2026-07-28 08:00 UTC may serve as prospective OOS"
            if bool(selected["eligible"])
            else (
                "no valid-sample train/validation-positive configuration; stop this "
                "surface without examining the already revealed window"
            )
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    pd.DataFrame(selected_result.trades).to_csv(TRADES_PATH, index=False)
    pd.DataFrame(selected_result.equity_path).to_csv(EQUITY_PATH, index=False)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
