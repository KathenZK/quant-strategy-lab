from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import sds_engine as engine


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SUMMARY_PATH = ARTIFACT_DIR / "hype_15m_sds_regression_prefit_search.json"
RANKING_PATH = ARTIFACT_DIR / "hype_15m_sds_regression_prefit_ranking.csv"
CANDIDATE_TRADES_PATH = (
    ARTIFACT_DIR / "hype_15m_sds_regression_prefit_candidate_trades.csv"
)
CANDIDATE_EQUITY_PATH = (
    ARTIFACT_DIR / "hype_15m_sds_regression_prefit_candidate_equity.csv"
)


def regression_features(
    book: engine.FeatureBook,
    window: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    log_price = np.log(book.close)
    rows = len(log_price)
    x_values = np.arange(window, dtype="float64")
    x_mean = float(x_values.mean())
    centered_x = x_values - x_mean
    sxx = float(np.sum(centered_x * centered_x))
    series = pd.Series(log_price)
    sum_y = series.rolling(window, min_periods=window).sum().to_numpy("float64")
    sum_y2 = (
        pd.Series(log_price * log_price)
        .rolling(window, min_periods=window)
        .sum()
        .to_numpy("float64")
    )
    rolling_xy = np.convolve(log_price, x_values[::-1], mode="valid")
    full_xy = np.full(rows, np.nan)
    full_xy[window - 1 :] = rolling_xy
    slope = (full_xy - x_mean * sum_y) / sxx
    syy = sum_y2 - sum_y * sum_y / window
    residual_ss = np.maximum(syy - slope * slope * sxx, 1e-18)
    slope_se = np.sqrt(residual_ss / (window - 2) / sxx)
    slope_t = slope / slope_se
    efficiency = engine._efficiency_ratio(log_price, window)
    prior_high = (
        pd.Series(book.high)
        .shift(1)
        .rolling(window, min_periods=window)
        .max()
        .to_numpy("float64")
    )
    prior_low = (
        pd.Series(book.low)
        .shift(1)
        .rolling(window, min_periods=window)
        .min()
        .to_numpy("float64")
    )
    location = (book.close - prior_low) / np.where(
        prior_high > prior_low,
        prior_high - prior_low,
        np.nan,
    )
    return slope_t, efficiency, location


def regression_states(
    features: tuple[np.ndarray, np.ndarray, np.ndarray],
    *,
    slope_t_entry: float,
    efficiency_min: float,
    location_min: float,
    start_confirm_bars: int,
    end_confirm_bars: int,
    slope_t_exit: float,
) -> engine.StateBook:
    slope_t, efficiency, location = features
    rows = len(slope_t)
    desired = np.zeros(rows, dtype="int8")
    reasons = ["warmup"] * rows
    state = 0
    long_count = 0
    short_count = 0
    weak_count = 0
    for index in range(rows):
        if not (
            np.isfinite(slope_t[index])
            and np.isfinite(efficiency[index])
            and np.isfinite(location[index])
        ):
            desired[index] = state
            continue
        long_ready = (
            slope_t[index] >= slope_t_entry
            and efficiency[index] >= efficiency_min
            and location[index] >= location_min
        )
        short_ready = (
            slope_t[index] <= -slope_t_entry
            and efficiency[index] >= efficiency_min
            and location[index] <= 1.0 - location_min
        )
        long_count = long_count + 1 if long_ready else 0
        short_count = short_count + 1 if short_ready else 0
        next_state = state
        reason = "hold"
        if state == 0:
            if long_count >= start_confirm_bars:
                next_state = 1
                reason = "long_start"
                weak_count = 0
            elif short_count >= start_confirm_bars:
                next_state = -1
                reason = "short_start"
                weak_count = 0
        elif state == 1:
            if short_count >= start_confirm_bars:
                next_state = -1
                reason = "long_to_short"
                weak_count = 0
            else:
                weak_count = weak_count + 1 if slope_t[index] <= slope_t_exit else 0
                if weak_count >= end_confirm_bars:
                    next_state = 0
                    reason = "long_end"
                    weak_count = 0
        else:
            if long_count >= start_confirm_bars:
                next_state = 1
                reason = "short_to_long"
                weak_count = 0
            else:
                weak_count = (
                    weak_count + 1 if slope_t[index] >= -slope_t_exit else 0
                )
                if weak_count >= end_confirm_bars:
                    next_state = 0
                    reason = "short_end"
                    weak_count = 0
        if next_state != state:
            state = next_state
            long_count = 0
            short_count = 0
        desired[index] = state
        reasons[index] = reason

    zeros = np.zeros(rows, dtype="float64")
    return engine.StateBook(
        desired_state=desired,
        normalized_return=zeros.copy(),
        fast_drift=slope_t.copy(),
        slow_drift=zeros.copy(),
        efficiency_ratio=efficiency,
        positive_cusum=location.copy(),
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
    windows = (48, 96, 144)
    feature_books = {window: regression_features(book, window) for window in windows}
    rows: list[dict[str, object]] = []
    backtest_config = engine.Config(stop_atr=6.0, max_hold_bars=384, leverage=1.0)
    grid = itertools.product(
        windows,
        (1.5, 2.0, 2.5),
        (0.20, 0.30, 0.40),
        (0.65, 0.75),
        (2, 3),
        (3, 5),
        (0.0, 0.5),
    )
    for (
        window,
        slope_t_entry,
        efficiency_min,
        location_min,
        start_confirm_bars,
        end_confirm_bars,
        slope_t_exit,
    ) in grid:
        states = regression_states(
            feature_books[window],
            slope_t_entry=slope_t_entry,
            efficiency_min=efficiency_min,
            location_min=location_min,
            start_confirm_bars=start_confirm_bars,
            end_confirm_bars=end_confirm_bars,
            slope_t_exit=slope_t_exit,
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
                "window": window,
                "slope_t_entry": slope_t_entry,
                "efficiency_min": efficiency_min,
                "location_min": location_min,
                "start_confirm_bars": start_confirm_bars,
                "end_confirm_bars": end_confirm_bars,
                "slope_t_exit": slope_t_exit,
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
    candidate_row = ranking.iloc[0].to_dict()
    candidate_states = regression_states(
        feature_books[int(candidate_row["window"])],
        slope_t_entry=float(candidate_row["slope_t_entry"]),
        efficiency_min=float(candidate_row["efficiency_min"]),
        location_min=float(candidate_row["location_min"]),
        start_confirm_bars=int(candidate_row["start_confirm_bars"]),
        end_confirm_bars=int(candidate_row["end_confirm_bars"]),
        slope_t_exit=float(candidate_row["slope_t_exit"]),
    )
    candidate_result = engine.run_backtest(
        book,
        backtest_config,
        states=candidate_states,
    )
    summary = {
        "family": "HYPE-15M-Sequential-Drift-State",
        "status": "explore / prefit-only / not promoted / not live-ready",
        "locked_oos_loaded": False,
        "locked_oos_retested": False,
        "search_space_size": int(len(ranking)),
        "train_end_exclusive": validation_start.isoformat(),
        "validation_end_exclusive": book.terminal_ts.isoformat(),
        "joint_positive_count": int(ranking["joint_positive"].sum()),
        "eligible_count": int(ranking["eligible"].sum()),
        "candidate_role": (
            "eligible prefit candidate"
            if bool(candidate_row["eligible"])
            else "best valid-sample failure comparator"
        ),
        "candidate": candidate_row,
        "candidate_metrics": candidate_result.metrics,
        "decision": (
            "no valid-sample configuration was positive in both train and validation; "
            "stop this search surface and do not evaluate it on the already revealed "
            "locked window"
            if not bool(candidate_row["eligible"])
            else (
                "prefit research candidate only; freeze for prospective OOS after "
                "2026-07-28 and do not evaluate on the already revealed locked window"
            )
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    pd.DataFrame(candidate_result.trades).to_csv(
        CANDIDATE_TRADES_PATH,
        index=False,
    )
    pd.DataFrame(candidate_result.equity_path).to_csv(
        CANDIDATE_EQUITY_PATH,
        index=False,
    )
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
