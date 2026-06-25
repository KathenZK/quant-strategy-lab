from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_pbtr_v2_ablation_slices import LEVERAGE, metric_with_sides
from research_hype_5m_pbtr_v5_executable_search import (
    END_TS,
    ENTRY_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    V5Config,
    add_features,
    apply_exit_cost,
    base_pullback_signal,
    crossed_stop,
    observation_signal,
    simulate_executable,
    touched_stop,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m


REPORT_PATH = Path("reports/hype_5m_pbtr_v51_event_quality.json")
SUMMARY_PATH = Path("reports/hype_5m_pbtr_v51_event_quality_summary.csv")
EXACT_RULES_PATH = Path("reports/hype_5m_pbtr_v51_event_quality_exact_rules.csv")
MARKDOWN_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v5-1-event-quality-2026-06-24.md"
)

IS_END = pd.Timestamp("2026-03-01T00:00:00Z")
VAL_END = pd.Timestamp("2026-06-01T00:00:00Z")
MIN_TRAIN_EVENTS = 120
BEAM_WIDTH = 180
EXACT_TOP = 450


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def add_quality_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"]
    high = result["high"]
    low = result["low"]
    open_ = result["open"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    for window in (3, 6, 12, 24, 48, 96, 192, 384):
        result[f"roc{window}"] = close / close.shift(window) - 1.0
    result["range_atr"] = (high - low) / result["atr14"]
    result["body_bps"] = (close / open_ - 1.0) * 10000.0
    result["abs_body_atr"] = (close - open_).abs() / result["atr14"]
    candle_top = pd.concat([open_, close], axis=1).max(axis=1)
    candle_bottom = pd.concat([open_, close], axis=1).min(axis=1)
    result["upper_wick_atr"] = (high - candle_top) / result["atr14"]
    result["lower_wick_atr"] = (candle_bottom - low) / result["atr14"]
    result["vol_ratio_96"] = result["volume"] / result["volume"].rolling(96, min_periods=96).mean()
    result["quote_vol_ratio_96"] = result["quote_volume"] / result["quote_volume"].rolling(96, min_periods=96).mean()
    result["trade_count_ratio_96"] = result["trade_count"] / result["trade_count"].rolling(96, min_periods=96).mean()
    result["atr_bps"] = result["atr14"] / close * 10000.0
    result["atr_ratio_14_96"] = result["atr14"] / result["atr14"].rolling(96, min_periods=96).mean()
    sum_tr = tr.rolling(14, min_periods=14).sum()
    high_14 = high.rolling(14, min_periods=14).max()
    low_14 = low.rolling(14, min_periods=14).min()
    result["chop14"] = 100.0 * np.log10(sum_tr / (high_14 - low_14).replace(0.0, np.nan)) / np.log10(14)
    return result


def regime_age(direction: np.ndarray) -> np.ndarray:
    age = np.zeros(len(direction), dtype=np.int32)
    current = 0
    start = 0
    for idx, value in enumerate(direction):
        if value == 0 or value != current:
            current = int(value)
            start = idx
        age[idx] = idx - start
    return age


def baseline_configs() -> list[V5Config]:
    return [
        V5Config(
            model="protected_entry",
            ema_fast=21,
            ema_slow=96,
            pullback_buffer=0.01,
            stop_atr=3.0,
            trail_atr=4.0,
            time_exit_bars=48,
            htf_threshold=None,
        ),
        V5Config(
            model="protected_entry",
            ema_fast=21,
            ema_slow=96,
            pullback_buffer=0.01,
            stop_atr=2.0,
            trail_atr=4.0,
            time_exit_bars=48,
            htf_threshold=None,
        ),
        V5Config(
            model="protected_entry",
            ema_fast=21,
            ema_slow=55,
            pullback_buffer=0.01,
            stop_atr=2.0,
            trail_atr=4.0,
            time_exit_bars=24,
            htf_threshold=0.5,
        ),
        V5Config(
            model="observe_then_enter",
            ema_fast=21,
            ema_slow=96,
            pullback_buffer=0.01,
            stop_atr=2.0,
            trail_atr=3.0,
            time_exit_bars=24,
            htf_threshold=None,
            observation_bars=3,
            min_favorable_bps=40.0,
            max_adverse_bps=100.0,
        ),
        V5Config(
            model="observe_then_enter",
            ema_fast=21,
            ema_slow=96,
            pullback_buffer=0.01,
            stop_atr=2.0,
            trail_atr=3.0,
            time_exit_bars=24,
            htf_threshold=None,
            observation_bars=3,
            min_favorable_bps=0.0,
            max_adverse_bps=100.0,
        ),
    ]


def build_signal(frame: pd.DataFrame, cfg: V5Config) -> tuple[np.ndarray, np.ndarray]:
    trigger = base_pullback_signal(frame, cfg)
    signal = observation_signal(frame, trigger, cfg)
    return trigger, signal


def build_event_frame(frame: pd.DataFrame, cfg: V5Config, signal: np.ndarray) -> pd.DataFrame:
    sig_idx = np.flatnonzero(signal)
    side = signal[sig_idx].astype("float64")
    close = frame["close"].to_numpy("float64")
    ema_fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{cfg.ema_slow}"].to_numpy("float64")
    spread = ema_fast - ema_slow
    direction = np.where(np.isfinite(spread), np.sign(spread), 0).astype(np.int8)
    age = regime_age(direction)
    ts = pd.to_datetime(frame["ts"])
    data: dict[str, np.ndarray] = {
        "idx": sig_idx,
        "signal_ts": frame["ts"].to_numpy()[sig_idx],
        "side": side,
        "hour": ts.dt.hour.to_numpy()[sig_idx].astype("float64"),
        "day_of_week": ts.dt.dayofweek.to_numpy()[sig_idx].astype("float64"),
        "ema_spread_bps": side * spread[sig_idx] / close[sig_idx] * 10000.0,
        "abs_ema_spread_bps": np.abs(spread[sig_idx] / close[sig_idx] * 10000.0),
        "htf_spread_bps": side * frame["htf_spread"].to_numpy("float64")[sig_idx] / close[sig_idx] * 10000.0,
        "dist_ema_bps": side * (close[sig_idx] / ema_fast[sig_idx] - 1.0) * 10000.0,
        "abs_dist_ema_bps": np.abs(close[sig_idx] / ema_fast[sig_idx] - 1.0) * 10000.0,
        "atr_bps": frame["atr_bps"].to_numpy("float64")[sig_idx],
        "atr_ratio_14_96": frame["atr_ratio_14_96"].to_numpy("float64")[sig_idx],
        "chop14": frame["chop14"].to_numpy("float64")[sig_idx],
        "range_atr": frame["range_atr"].to_numpy("float64")[sig_idx],
        "abs_body_atr": frame["abs_body_atr"].to_numpy("float64")[sig_idx],
        "dir_body_bps": side * frame["body_bps"].to_numpy("float64")[sig_idx],
        "dir_upper_wick_atr": np.where(
            side > 0,
            frame["upper_wick_atr"].to_numpy("float64")[sig_idx],
            frame["lower_wick_atr"].to_numpy("float64")[sig_idx],
        ),
        "opp_wick_atr": np.where(
            side > 0,
            frame["lower_wick_atr"].to_numpy("float64")[sig_idx],
            frame["upper_wick_atr"].to_numpy("float64")[sig_idx],
        ),
        "vol_ratio_96": frame["vol_ratio_96"].to_numpy("float64")[sig_idx],
        "quote_vol_ratio_96": frame["quote_vol_ratio_96"].to_numpy("float64")[sig_idx],
        "trade_count_ratio_96": frame["trade_count_ratio_96"].to_numpy("float64")[sig_idx],
        "regime_age": age[sig_idx].astype("float64"),
    }
    for window in (3, 6, 12, 24, 48, 96, 192, 384):
        data[f"dir_roc{window}_bps"] = side * frame[f"roc{window}"].to_numpy("float64")[sig_idx] * 10000.0
    return pd.DataFrame(data)


def simulate_independent_events(frame: pd.DataFrame, signal: np.ndarray, cfg: V5Config) -> pd.DataFrame:
    sig_idx = np.flatnonzero(signal)
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    n = len(frame)
    rows: list[dict[str, Any]] = []
    for idx in sig_idx:
        side = int(signal[idx])
        entry_i = idx + 1
        if entry_i >= n or side == 0:
            continue
        signal_atr = float(atr[idx])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        entry_price = float(open_[entry_i] * (1.0 + side * ENTRY_SLIPPAGE_RATE))
        active_stop = entry_price - side * cfg.stop_atr * signal_atr
        end_i = min(n - 1, entry_i + cfg.time_exit_bars - 1)
        raw_exit_price = float(close[end_i])
        exit_i = end_i
        reason = "time"
        peak = entry_price
        trough = entry_price
        for bar_i in range(entry_i, end_i + 1):
            if crossed_stop(float(open_[bar_i]), active_stop, side):
                raw_exit_price = float(open_[bar_i])
                exit_i = bar_i
                reason = "gap_market_exit"
                break
            if touched_stop(float(high[bar_i]), float(low[bar_i]), active_stop, side):
                raw_exit_price = float(active_stop)
                exit_i = bar_i
                reason = "stop_market"
                break
            if side > 0:
                peak = max(peak, float(high[bar_i]))
                if np.isfinite(atr[bar_i]) and cfg.trail_atr > 0:
                    active_stop = max(active_stop, peak - cfg.trail_atr * float(atr[bar_i]))
            else:
                trough = min(trough, float(low[bar_i]))
                if np.isfinite(atr[bar_i]) and cfg.trail_atr > 0:
                    active_stop = min(active_stop, trough + cfg.trail_atr * float(atr[bar_i]))
        exit_price = apply_exit_cost(raw_exit_price, side)
        gross = side * (exit_price / entry_price - 1.0)
        fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
        rows.append(
            {
                "idx": int(idx),
                "entry_idx": int(entry_i),
                "exit_idx": int(exit_i),
                "event_net_ret_1x": float(gross - fee_cost),
                "event_reason": reason,
            }
        )
    return pd.DataFrame(rows)


def approximate_metrics(returns: np.ndarray) -> dict[str, float | int]:
    clean = returns[np.isfinite(returns)]
    if len(clean) == 0:
        return {"trades": 0, "profit_factor": 0.0, "avg_trade": 0.0, "win_rate": 0.0, "payoff_ratio": 0.0}
    wins = clean[clean > 0]
    losses = clean[clean <= 0]
    profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf")
    payoff = float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) else 0.0
    return {
        "trades": int(len(clean)),
        "profit_factor": profit_factor,
        "avg_trade": float(clean.mean()),
        "win_rate": float((clean > 0).mean()),
        "payoff_ratio": payoff,
    }


def atomic_rules(events: pd.DataFrame, train_mask: np.ndarray) -> list[tuple[str, np.ndarray]]:
    rules: list[tuple[str, np.ndarray]] = []
    quantiles = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95)
    excluded = {"idx", "signal_ts", "entry_idx", "exit_idx", "event_net_ret_1x", "event_reason"}
    for column in events.columns:
        if column in excluded:
            continue
        values = events[column].to_numpy("float64")
        finite_train = np.isfinite(values) & train_mask
        if int(finite_train.sum()) < MIN_TRAIN_EVENTS * 2:
            continue
        train_values = values[finite_train]
        for quantile in quantiles:
            threshold = float(np.quantile(train_values, quantile))
            for op in ("<=", ">="):
                keep = (values <= threshold) if op == "<=" else (values >= threshold)
                keep &= np.isfinite(values)
                train_count = int((keep & train_mask).sum())
                if MIN_TRAIN_EVENTS <= train_count <= int(train_mask.sum()) - MIN_TRAIN_EVENTS:
                    rules.append((f"{column} {op} {threshold:.6g}", keep))
    return rules


def filtered_signal(signal: np.ndarray, events: pd.DataFrame, keep: np.ndarray) -> np.ndarray:
    result = np.zeros_like(signal)
    idx = events["idx"].to_numpy("int64")
    result[idx[np.asarray(keep, dtype=bool)]] = signal[idx[np.asarray(keep, dtype=bool)]]
    previous_same = np.r_[False, (result[1:] != 0) & (result[1:] == result[:-1])]
    result[previous_same] = 0
    return result


def spans(frame: pd.DataFrame) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return {
        "is": (start, IS_END),
        "val": (IS_END, VAL_END),
        "fwd": (VAL_END, end),
        "full": (start, end),
    }


def exact_metrics(frame: pd.DataFrame, signal: np.ndarray, cfg: V5Config, items: dict[str, tuple[pd.Timestamp, pd.Timestamp]]) -> dict[str, Any]:
    trades, _ = simulate_executable(frame, signal, cfg)
    result: dict[str, Any] = {}
    for name, (start, end) in items.items():
        metrics = metric_with_sides(trades, LEVERAGE, start=start, end=end)
        for key, value in metrics.items():
            result[f"{name}_{key}"] = value
    return result


def rule_score(metrics: dict[str, float | int]) -> float:
    if int(metrics["trades"]) < MIN_TRAIN_EVENTS:
        return -1e9
    profit_factor = float(metrics["profit_factor"])
    payoff = float(metrics["payoff_ratio"])
    if not np.isfinite(profit_factor):
        profit_factor = 5.0
    if not np.isfinite(payoff):
        payoff = 5.0
    return (
        min(profit_factor, 3.0) * 100.0
        + float(metrics["avg_trade"]) * 10000.0
        + min(payoff, 5.0) * 8.0
        + float(metrics["win_rate"]) * 20.0
    )


def feature_names(rule: str) -> set[str]:
    names: set[str] = set()
    for part in rule.split(" & "):
        names.add(part.split(" <= ")[0].split(" >= ")[0])
    return names


def mine_rules(events: pd.DataFrame, train_mask: np.ndarray) -> list[tuple[float, str, np.ndarray, dict[str, float | int]]]:
    rules = atomic_rules(events, train_mask)
    returns = events["event_net_ret_1x"].to_numpy("float64")
    candidates: list[tuple[float, str, np.ndarray, dict[str, float | int]]] = []
    beam: list[tuple[float, str, np.ndarray, dict[str, float | int]]] = []
    for description, keep in rules:
        metrics = approximate_metrics(returns[keep & train_mask])
        beam.append((rule_score(metrics), description, keep, metrics))
    beam = sorted(beam, key=lambda item: item[0], reverse=True)[:BEAM_WIDTH]
    candidates.extend(beam)
    for _depth in (2, 3, 4):
        new_rows: list[tuple[float, str, np.ndarray, dict[str, float | int]]] = []
        seen: set[tuple[str, ...]] = set()
        for _score, description, keep, _metrics in beam:
            used_features = feature_names(description)
            for atom_description, atom_keep in rules:
                atom_feature = next(iter(feature_names(atom_description)))
                if atom_feature in used_features:
                    continue
                new_keep = keep & atom_keep
                if int((new_keep & train_mask).sum()) < MIN_TRAIN_EVENTS:
                    continue
                parts = tuple(sorted((description + " & " + atom_description).split(" & ")))
                if parts in seen:
                    continue
                seen.add(parts)
                metrics = approximate_metrics(returns[new_keep & train_mask])
                new_rows.append((rule_score(metrics), description + " & " + atom_description, new_keep, metrics))
        beam = sorted(new_rows, key=lambda item: item[0], reverse=True)[:BEAM_WIDTH]
        candidates.extend(beam)
    return sorted(candidates, key=lambda item: item[0], reverse=True)[:EXACT_TOP]


def eval_baseline(frame: pd.DataFrame, cfg: V5Config, span_items: dict[str, tuple[pd.Timestamp, pd.Timestamp]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    trigger, signal = build_signal(frame, cfg)
    events = build_event_frame(frame, cfg, signal)
    independent = simulate_independent_events(frame, signal, cfg)
    events = events.merge(independent, on="idx", how="inner")
    signal_ts = pd.to_datetime(events["signal_ts"], utc=True)
    train_mask = (signal_ts < IS_END).to_numpy()
    mined = mine_rules(events, train_mask)

    baseline_metrics = exact_metrics(frame, signal, cfg, span_items)
    baseline_summary = {
        "label": cfg.label,
        "model": cfg.model,
        "trigger_count": int(np.count_nonzero(trigger)),
        "signal_count": int(np.count_nonzero(signal)),
        "event_count": int(len(events)),
        **asdict(cfg),
        **baseline_metrics,
    }

    exact_rows: list[dict[str, Any]] = []
    seen_rules: set[str] = set()
    for approximate_score, rule, keep, approx_is in mined:
        if rule in seen_rules:
            continue
        seen_rules.add(rule)
        selected_signal = filtered_signal(signal, events, keep)
        row = {
            "baseline": cfg.label,
            "rule": rule,
            "depth": len(rule.split(" & ")),
            "approx_score": approximate_score,
            **{f"approx_is_{key}": value for key, value in approx_is.items()},
            **asdict(cfg),
            **exact_metrics(frame, selected_signal, cfg, span_items),
        }
        row["selected_event_count"] = int(np.count_nonzero(keep))
        row["selected_train_events"] = int(np.count_nonzero(keep & train_mask))
        row["full_trades_per_month"] = float(row["full_trades"]) / max(
            (span_items["full"][1] - span_items["full"][0]).days / 30.4375,
            1.0,
        )
        row["passes_quality_gate"] = (
            int(row["full_trades"]) >= 180
            and int(row["is_trades"]) >= 80
            and int(row["val_trades"]) >= 30
            and int(row["fwd_trades"]) >= 8
            and float(row["full_profit_factor"]) >= 1.25
            and float(row["is_profit_factor"]) >= 1.15
            and float(row["val_profit_factor"]) >= 1.05
            and float(row["full_avg_trade"]) > 0
            and float(row["full_payoff_ratio"]) > 1.0
            and float(row["full_max_dd"]) >= -0.25
        )
        row["watchlist"] = (
            int(row["full_trades"]) >= 50
            and int(row["is_trades"]) >= 30
            and int(row["val_trades"]) >= 10
            and float(row["full_profit_factor"]) >= 1.50
            and float(row["is_profit_factor"]) >= 1.30
            and float(row["val_profit_factor"]) >= 1.05
            and float(row["full_avg_trade"]) > 0
            and float(row["full_max_dd"]) >= -0.20
        )
        row["inspection_score"] = (
            min(float(row["full_profit_factor"]), 3.0) * 80.0
            + min(float(row["val_profit_factor"]), 3.0) * 60.0
            + min(float(row["fwd_profit_factor"]), 3.0) * 20.0
            + float(row["full_avg_trade"]) * 10000.0
            + float(row["full_max_dd"]) * 20.0
            + min(int(row["full_trades"]), 300) * 0.15
        )
        exact_rows.append(row)
    return baseline_summary, exact_rows


def render_rule_table(rows: pd.DataFrame, limit: int = 12) -> list[str]:
    if rows.empty:
        return ["No rows."]
    lines = [
        "| baseline | rule | trades | PF | IS PF | VAL PF | FWD PF | win | payoff | avg | DD | freq/mo |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{row['baseline']}` | `{row['rule']}` | `{int(row['full_trades'])}` | "
            f"`{num(float(row['full_profit_factor']))}` | `{num(float(row['is_profit_factor']))}` | "
            f"`{num(float(row['val_profit_factor']))}` | `{num(float(row['fwd_profit_factor']))}` | "
            f"`{pct(float(row['full_win_rate']))}` | `{num(float(row['full_payoff_ratio']))}` | "
            f"`{pct(float(row['full_avg_trade']))}` | `{pct(float(row['full_max_dd']))}` | "
            f"`{float(row['full_trades_per_month']):.1f}` |"
        )
    return lines


def render_baseline_table(rows: pd.DataFrame) -> list[str]:
    lines = [
        "| baseline | model | trigger | signal/events | trades | PF | win | payoff | avg | DD |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['model']}` | `{int(row['trigger_count'])}` | `{int(row['event_count'])}` | "
            f"`{int(row['full_trades'])}` | `{num(float(row['full_profit_factor']))}` | "
            f"`{pct(float(row['full_win_rate']))}` | `{num(float(row['full_payoff_ratio']))}` | "
            f"`{pct(float(row['full_avg_trade']))}` | `{pct(float(row['full_max_dd']))}` |"
        )
    return lines


def render_markdown(baselines: pd.DataFrame, exact: pd.DataFrame) -> str:
    passed = exact.loc[exact["passes_quality_gate"]].sort_values("inspection_score", ascending=False)
    watch = exact.loc[exact["watchlist"] & ~exact["passes_quality_gate"]].sort_values("inspection_score", ascending=False)
    top = exact.sort_values("inspection_score", ascending=False)
    higher_freq = exact.loc[exact["full_trades"].ge(180)].sort_values(
        ["full_profit_factor", "val_profit_factor"],
        ascending=[False, False],
    )
    lines = [
        "# HYPE-5M-PBTR-V5.1 Event Quality Search 2026-06-24",
        "",
        "Family id: `HYPE-5M-PBTR`",
        "",
        "V5.1 keeps the existing pullback signal trigger as an event generator and adds a separate quality-selection layer. The final evaluation still replays executable orders after filtering, so overlapping signals, immediate protective stops, market exits on crossed stops, observed fees, and observed slippage remain in the result.",
        "",
        "## Why This Exists",
        "",
        "V5 showed that `trigger -> enter` is negative under live-realistic execution. The trigger is still useful because it generates many candidate events. The question here is whether event-time features can select a smaller set of signals with positive executable expectancy.",
        "",
        "## Baselines Before Filtering",
        "",
        *render_baseline_table(baselines),
        "",
        "## Gate",
        "",
        "- Candidate: full trades `>=180`, IS trades `>=80`, validation trades `>=30`, forward trades `>=8`, full PF `>=1.25`, IS PF `>=1.15`, validation PF `>=1.05`, average trade `>0`, payoff `>1`, max drawdown no worse than `-25%`.",
        "- Watchlist: full trades `>=50`, IS trades `>=30`, validation trades `>=10`, full PF `>=1.50`, IS PF `>=1.30`, validation PF `>=1.05`, average trade `>0`, max drawdown no worse than `-20%`.",
        "",
        "The search mines conjunction rules on the IS period only using independent event outcomes, then each mined rule is replayed exactly as a live executable strategy.",
        "",
        "## Passing Candidates",
        "",
        *render_rule_table(passed, limit=12),
        "",
        "## Watchlist",
        "",
        *render_rule_table(watch, limit=12),
        "",
        "## Best Exact Replays",
        "",
        *render_rule_table(top, limit=12),
        "",
        "## Higher-Frequency Rows",
        "",
        "Rows with at least `180` full-sample trades. These are closer to the desired validation cadence, but must still pass validation stability.",
        "",
        *render_rule_table(higher_freq, limit=12),
        "",
        "## Interpretation",
        "",
    ]
    if len(passed):
        best = passed.iloc[0]
        lines.extend(
            [
                f"`{best['rule']}` is the first V5.1 event-quality candidate that passes the mechanical gate. It should not be promoted directly to live until ablation, rolling-window diagnostics, and side-specific replay are finished.",
            ]
        )
    elif len(watch):
        best = watch.iloc[0]
        lines.extend(
            [
                "No rule passed the candidate gate. The most interesting watchlist rules are not a repair of the old trailing model; they are a different hypothesis: long-only mature trend continuation after a pullback trigger.",
                "",
                f"The top watchlist rule is `{best['rule']}`. It has full PF `{num(float(best['full_profit_factor']))}`, validation PF `{num(float(best['val_profit_factor']))}`, average trade `{pct(float(best['full_avg_trade']))}`, and max drawdown `{pct(float(best['full_max_dd']))}`, but only `{int(best['full_trades'])}` full-sample trades (`{float(best['full_trades_per_month']):.1f}`/month). That is too sparse for the high-frequency live-validation goal.",
                "",
                "Higher-frequency observation rules can show positive full-sample PF, but their validation slice is still weak or negative. That shape looks like selection bias, not a live-ready signal-quality filter.",
            ]
        )
    else:
        lines.extend(
            [
                "No candidate or watchlist rule survived exact executable replay. The current trigger may still be useful as an event source, but simple mined quality rules are not enough.",
            ]
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "Do not draft a V5.1 live spec yet. The useful discovery is narrower: quality filtering can flip expectancy only when it selects rare, long-only, strong-trend continuation events. That improves tradability but sacrifices the high signal frequency that made the trigger attractive.",
            "",
            "Recommended next step: V5.2 should model signal quality as a walk-forward event-ranking problem. The live candidate should trade only if the same feature family keeps positive validation PF while maintaining a minimum trade cadence, rather than hand-picking a sparse high-PF subset.",
            "",
            "## Outputs",
            "",
            "- Script: `archive/scripts/research/research_hype_5m_pbtr_v51_event_quality.py`",
            f"- JSON: `{REPORT_PATH}`",
            f"- Baseline CSV: `{SUMMARY_PATH}`",
            f"- Exact rule CSV: `{EXACT_RULES_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= END_TS].reset_index(drop=True)
    frame = add_quality_features(add_features(raw))
    span_items = spans(frame)
    baseline_rows: list[dict[str, Any]] = []
    exact_rows: list[dict[str, Any]] = []
    for cfg in baseline_configs():
        baseline, rows = eval_baseline(frame, cfg, span_items)
        baseline_rows.append(baseline)
        exact_rows.extend(rows)
        print(f"finished {cfg.label}: exact_rules={len(rows)}", flush=True)

    baselines = pd.DataFrame(baseline_rows)
    exact = pd.DataFrame(exact_rows).sort_values("inspection_score", ascending=False)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    baselines.to_csv(SUMMARY_PATH, index=False)
    exact.to_csv(EXACT_RULES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(baselines, exact), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "baselines": baseline_rows,
                "exact_rules": exact_rows,
                "outputs": {
                    "summary_csv": str(SUMMARY_PATH),
                    "exact_rules_csv": str(EXACT_RULES_PATH),
                    "markdown": str(MARKDOWN_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
