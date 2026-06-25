from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import Trade
from research_hype_5m_pbtr_v2_ablation_slices import LEVERAGE, metric_with_sides
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    NET_SLIPPAGE_RATE_ON_TURNOVER,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m


END_TS = pd.Timestamp("2026-06-23T04:15:00Z")

REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v5_executable_search.json")
SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v5_executable_search_summary.csv")
SLICES_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v5_executable_search_slices.csv")
MARKDOWN_PATH = Path(
    "research/hype/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v5-executable-search-2026-06-24.md"
)


@dataclass(frozen=True, slots=True)
class V5Config:
    model: str
    ema_fast: int
    ema_slow: int
    pullback_buffer: float
    stop_atr: float
    trail_atr: float
    time_exit_bars: int
    htf_threshold: float | None
    observation_bars: int = 0
    min_favorable_bps: float = 0.0
    max_adverse_bps: float | None = None

    @property
    def label(self) -> str:
        htf = "none" if self.htf_threshold is None else f"{self.htf_threshold:g}"
        adverse = "none" if self.max_adverse_bps is None else f"{self.max_adverse_bps:g}"
        return (
            f"{self.model}_ema{self.ema_fast}_{self.ema_slow}"
            f"_pb{self.pullback_buffer:g}"
            f"_sl{self.stop_atr:g}"
            f"_tr{self.trail_atr:g}"
            f"_tx{self.time_exit_bars}"
            f"_htf{htf}"
            f"_obs{self.observation_bars}"
            f"_fav{self.min_favorable_bps:g}"
            f"_adv{adverse}"
        )


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def validation_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return [
        {"name": "full", "start": start, "end": end},
        {"name": "2025_05_30_to_2025_09_01", "start": start, "end": pd.Timestamp("2025-09-01T00:00:00Z")},
        {
            "name": "2025_09_01_to_2025_12_01",
            "start": pd.Timestamp("2025-09-01T00:00:00Z"),
            "end": pd.Timestamp("2025-12-01T00:00:00Z"),
        },
        {
            "name": "2025_12_01_to_2026_03_01",
            "start": pd.Timestamp("2025-12-01T00:00:00Z"),
            "end": pd.Timestamp("2026-03-01T00:00:00Z"),
        },
        {
            "name": "2026_03_01_to_2026_06_01",
            "start": pd.Timestamp("2026-03-01T00:00:00Z"),
            "end": pd.Timestamp("2026-06-01T00:00:00Z"),
        },
        {
            "name": "2026_06_01_to_2026_06_23",
            "start": pd.Timestamp("2026-06-01T00:00:00Z"),
            "end": end,
        },
    ]


def month_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    boundaries = pd.date_range(start.floor("D").replace(day=1), end, freq="MS", tz="UTC")
    rows: list[dict[str, Any]] = []
    current = start
    for boundary in boundaries:
        if boundary <= start:
            continue
        rows.append({"name": current.strftime("%Y_%m"), "start": current, "end": min(boundary, end)})
        current = boundary
    if current < end:
        rows.append({"name": current.strftime("%Y_%m"), "start": current, "end": end})
    return rows


def weekly_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    rows: list[dict[str, Any]] = []
    idx = 1
    current = start
    while current < end:
        nxt = min(current + pd.Timedelta(days=7), end)
        rows.append({"name": f"week_{idx:03d}_{current:%Y%m%d}_{nxt:%Y%m%d}", "start": current, "end": nxt})
        current = nxt
        idx += 1
    return rows


def add_features(raw: pd.DataFrame) -> pd.DataFrame:
    result = raw.copy()
    result["_ts_ns"] = result["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    close = result["close"]
    high = result["high"]
    low = result["low"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    for span in (9, 13, 21, 55, 72, 96, 384):
        result[f"ema{span}"] = close.ewm(span=span, adjust=False, min_periods=span).mean()
    result["atr14"] = tr.rolling(14, min_periods=14).mean()
    result["htf_spread"] = result["ema96"] - result["ema384"]
    return result


def suppress_adjacent_same(signal: np.ndarray) -> np.ndarray:
    result = signal.copy()
    previous_same = np.r_[False, (result[1:] != 0) & (result[1:] == result[:-1])]
    result[previous_same] = 0
    return result


def base_pullback_signal(frame: pd.DataFrame, cfg: V5Config) -> np.ndarray:
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    ema_fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{cfg.ema_slow}"].to_numpy("float64")
    atr14 = frame["atr14"].to_numpy("float64")
    htf = frame["htf_spread"].to_numpy("float64")
    spread = ema_fast - ema_slow
    direction = np.where(np.isfinite(spread), np.sign(spread), 0).astype(np.int8)
    touched = np.where(
        direction > 0,
        low <= ema_fast * (1.0 + cfg.pullback_buffer),
        high >= ema_fast * (1.0 - cfg.pullback_buffer),
    )
    reclaimed = np.where(direction > 0, close > ema_fast, close < ema_fast)
    candle = np.where(direction > 0, close > open_, close < open_)
    mask = (direction != 0) & touched & reclaimed & candle & np.isfinite(atr14)
    if cfg.htf_threshold is not None:
        mask &= np.isfinite(htf) & (direction * htf >= cfg.htf_threshold)
    mask = np.nan_to_num(mask, nan=False).astype(bool)
    signal = np.zeros(len(frame), dtype=np.int8)
    signal[mask] = direction[mask]
    return suppress_adjacent_same(signal)


def observation_signal(frame: pd.DataFrame, trigger: np.ndarray, cfg: V5Config) -> np.ndarray:
    if cfg.model != "observe_then_enter":
        return trigger.copy()
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    ema_fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{cfg.ema_slow}"].to_numpy("float64")
    atr14 = frame["atr14"].to_numpy("float64")
    htf = frame["htf_spread"].to_numpy("float64")
    result = np.zeros(len(trigger), dtype=np.int8)
    n = len(trigger)
    for sig_i in np.flatnonzero(trigger):
        side = int(trigger[sig_i])
        initial_entry_i = sig_i + 1
        confirm_i = sig_i + cfg.observation_bars
        entry_i = confirm_i + 1
        if initial_entry_i >= n or confirm_i >= n or entry_i >= n:
            continue
        direction_now = 1 if ema_fast[confirm_i] > ema_slow[confirm_i] else -1 if ema_fast[confirm_i] < ema_slow[confirm_i] else 0
        if direction_now != side:
            continue
        if not np.isfinite(atr14[confirm_i]):
            continue
        if side > 0 and close[confirm_i] <= ema_fast[confirm_i]:
            continue
        if side < 0 and close[confirm_i] >= ema_fast[confirm_i]:
            continue
        if cfg.htf_threshold is not None and not (np.isfinite(htf[confirm_i]) and side * htf[confirm_i] >= cfg.htf_threshold):
            continue
        ref = float(open_[initial_entry_i])
        favorable_bps = float(side * (close[confirm_i] / ref - 1.0) * 10000.0)
        if favorable_bps < cfg.min_favorable_bps:
            continue
        if cfg.max_adverse_bps is not None:
            if side > 0:
                adverse_bps = float((np.nanmin(low[initial_entry_i : confirm_i + 1]) / ref - 1.0) * 10000.0)
            else:
                adverse_bps = float(side * (np.nanmax(high[initial_entry_i : confirm_i + 1]) / ref - 1.0) * 10000.0)
            if adverse_bps < -cfg.max_adverse_bps:
                continue
        if result[confirm_i] == 0:
            result[confirm_i] = side
    return suppress_adjacent_same(result)


def crossed_stop(open_price: float, stop_price: float, side: int) -> bool:
    return bool(open_price <= stop_price if side > 0 else open_price >= stop_price)


def touched_stop(high_price: float, low_price: float, stop_price: float, side: int) -> bool:
    return bool(low_price <= stop_price if side > 0 else high_price >= stop_price)


def apply_exit_cost(raw_exit_price: float, side: int) -> float:
    return float(raw_exit_price * (1.0 - side * EXIT_SLIPPAGE_RATE))


def simulate_executable(frame: pd.DataFrame, signal: np.ndarray, cfg: V5Config) -> tuple[list[Trade], dict[str, Any]]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Trade] = []
    reasons: dict[str, int] = {}
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        side = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= n or entry_i <= blocked_until or side == 0:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        entry_price = float(open_[entry_i] * (1.0 + side * ENTRY_SLIPPAGE_RATE))
        active_stop = entry_price - side * cfg.stop_atr * signal_atr
        end_i = min(n - 1, entry_i + cfg.time_exit_bars - 1)
        peak = entry_price
        trough = entry_price
        reason = "time"
        raw_exit_price = float(close[end_i])
        exit_i = end_i
        final_stop = active_stop

        for j in range(entry_i, end_i + 1):
            if crossed_stop(float(open_[j]), active_stop, side):
                reason = "gap_market_exit"
                raw_exit_price = float(open_[j])
                exit_i = j
                break
            if touched_stop(float(high[j]), float(low[j]), active_stop, side):
                reason = "stop_market"
                raw_exit_price = float(active_stop)
                exit_i = j
                break
            if side > 0:
                peak = max(peak, float(high[j]))
                if np.isfinite(atr[j]) and cfg.trail_atr > 0:
                    active_stop = max(active_stop, peak - cfg.trail_atr * float(atr[j]))
            else:
                trough = min(trough, float(low[j]))
                if np.isfinite(atr[j]) and cfg.trail_atr > 0:
                    active_stop = min(active_stop, trough + cfg.trail_atr * float(atr[j]))
            final_stop = active_stop

        exit_price = apply_exit_cost(raw_exit_price, side)
        gross = side * (exit_price / entry_price - 1.0)
        fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
        net = gross - fee_cost
        path_high = high[entry_i : exit_i + 1]
        path_low = low[entry_i : exit_i + 1]
        if side > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
        else:
            mae = float(np.nanmin(side * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(side * (path_low / entry_price - 1.0)))
        trades.append(
            Trade(
                config=cfg.label,
                signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                reason=reason,
                bars_held=int(exit_i - entry_i + 1),
                net_ret_1x=float(net),
                mae_1x=float(mae - FEE_RATE_PER_FILL),
                mfe_1x=float(mfe),
            )
        )
        reasons[reason] = reasons.get(reason, 0) + 1
        blocked_until = exit_i
        _ = final_stop

    total = max(len(trades), 1)
    return trades, {f"reason_{key}_rate": value / total for key, value in reasons.items()}


def build_configs() -> list[V5Config]:
    configs: list[V5Config] = []
    for ema_fast, ema_slow in ((21, 96), (13, 96), (9, 96), (21, 72), (21, 55)):
        for pullback_buffer in (0.01, 0.02):
            for stop_atr in (1.5, 2.0, 3.0):
                for trail_atr in (2.0, 3.0, 4.0):
                    for time_exit_bars in (24, 48, 96):
                        for htf_threshold in (None, 0.5):
                            configs.append(
                                V5Config(
                                    model="protected_entry",
                                    ema_fast=ema_fast,
                                    ema_slow=ema_slow,
                                    pullback_buffer=pullback_buffer,
                                    stop_atr=stop_atr,
                                    trail_atr=trail_atr,
                                    time_exit_bars=time_exit_bars,
                                    htf_threshold=htf_threshold,
                                )
                            )
    for ema_fast, ema_slow in ((21, 96), (9, 96), (21, 55)):
        for observation_bars in (1, 3, 6, 9, 12):
            for min_favorable_bps in (0.0, 20.0, 40.0):
                for max_adverse_bps in (100.0, 200.0):
                    for stop_atr in (1.5, 2.0):
                        for trail_atr in (2.0, 3.0):
                            for time_exit_bars in (24, 48):
                                for htf_threshold in (None, 0.5):
                                    configs.append(
                                        V5Config(
                                            model="observe_then_enter",
                                            ema_fast=ema_fast,
                                            ema_slow=ema_slow,
                                            pullback_buffer=0.01,
                                            stop_atr=stop_atr,
                                            trail_atr=trail_atr,
                                            time_exit_bars=time_exit_bars,
                                            htf_threshold=htf_threshold,
                                            observation_bars=observation_bars,
                                            min_favorable_bps=min_favorable_bps,
                                            max_adverse_bps=max_adverse_bps,
                                        )
                                    )
    return configs


def evaluate_config(
    frame: pd.DataFrame,
    cfg: V5Config,
    slices: list[dict[str, Any]],
    month_items: list[dict[str, Any]],
    week_items: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    trigger = base_pullback_signal(frame, cfg)
    signal = observation_signal(frame, trigger, cfg)
    trades, reason_stats = simulate_executable(frame, signal, cfg)
    start = slices[0]["start"]
    end = slices[0]["end"]
    full = metric_with_sides(trades, LEVERAGE, start=start, end=end)
    slice_rows: list[dict[str, Any]] = []
    min_pf = float("inf")
    min_win = 1.0
    worst_dd = 0.0
    min_avg_trade = float("inf")
    for item in slices:
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        slice_rows.append(
            {
                "label": cfg.label,
                "model": cfg.model,
                "slice": item["name"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metrics,
            }
        )
        min_pf = min(min_pf, float(metrics["profit_factor"]))
        min_win = min(min_win, float(metrics["win_rate"]))
        worst_dd = min(worst_dd, float(metrics["max_dd"]))
        min_avg_trade = min(min_avg_trade, float(metrics["avg_trade"]))

    profitable_months = 0
    for item in month_items:
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        profitable_months += int(float(metrics["total_return"]) > 0)
    profitable_weeks = 0
    for item in week_items:
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        profitable_weeks += int(float(metrics["total_return"]) > 0)

    summary = {
        "label": cfg.label,
        "model": cfg.model,
        "trigger_count": int(np.count_nonzero(trigger)),
        "signal_count": int(np.count_nonzero(signal)),
        "trade_count": int(len(trades)),
        **asdict(cfg),
        **{f"full_{key}": value for key, value in full.items()},
        "min_slice_profit_factor": min_pf,
        "min_slice_win_rate": min_win,
        "worst_slice_max_dd": worst_dd,
        "min_slice_avg_trade": min_avg_trade,
        "profitable_months": profitable_months,
        "month_count": len(month_items),
        "profitable_weeks": profitable_weeks,
        "week_count": len(week_items),
        **reason_stats,
    }
    summary["passes_v5_gate"] = (
        int(summary["full_trades"]) >= 500
        and float(summary["full_profit_factor"]) >= 1.30
        and float(summary["min_slice_profit_factor"]) >= 1.05
        and float(summary["full_payoff_ratio"]) >= 1.20
        and float(summary["full_avg_trade"]) > 0
        and float(summary["full_max_dd"]) >= -0.25
        and profitable_months >= 8
    )
    summary["watchlist"] = (
        int(summary["full_trades"]) >= 500
        and float(summary["full_profit_factor"]) >= 1.0
        and float(summary["full_avg_trade"]) > 0
        and float(summary["full_max_dd"]) >= -0.50
    )
    summary["score"] = (
        100.0 * min(float(summary["full_profit_factor"]), 2.0)
        + 50.0 * min(float(summary["min_slice_profit_factor"]), 1.5)
        + 30.0 * float(summary["full_payoff_ratio"])
        + 1000.0 * float(summary["full_avg_trade"])
        + 30.0 * float(summary["full_max_dd"])
        + 2.0 * profitable_months
    )
    return summary, slice_rows


def render_table(rows: pd.DataFrame, limit: int = 20) -> list[str]:
    if rows.empty:
        return ["No rows."]
    lines = [
        "| model | EMA | obs | fav | adv | stop | trail | time | htf | trades | PF | minPF | win | payoff | avg | DD | months |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        htf = "none" if pd.isna(row["htf_threshold"]) else f"{float(row['htf_threshold']):g}"
        adv = "none" if pd.isna(row["max_adverse_bps"]) else f"{float(row['max_adverse_bps']):g}"
        lines.append(
            f"| `{row['model']}` | `{int(row['ema_fast'])}/{int(row['ema_slow'])}` | `{int(row['observation_bars'])}` | "
            f"`{float(row['min_favorable_bps']):.0f}` | `{adv}` | `{float(row['stop_atr']):g}` | `{float(row['trail_atr']):g}` | "
            f"`{int(row['time_exit_bars'])}` | `{htf}` | `{int(row['full_trades'])}` | `{num(float(row['full_profit_factor']))}` | "
            f"`{num(float(row['min_slice_profit_factor']))}` | `{pct(float(row['full_win_rate']))}` | `{num(float(row['full_payoff_ratio']))}` | "
            f"`{pct(float(row['full_avg_trade']))}` | `{pct(float(row['full_max_dd']))}` | `{int(row['profitable_months'])}/{int(row['month_count'])}` |"
        )
    return lines


def render_markdown(summary: pd.DataFrame) -> str:
    passed = summary.loc[summary["passes_v5_gate"]].sort_values("score", ascending=False)
    watch = summary.loc[summary["watchlist"] & ~summary["passes_v5_gate"]].sort_values(
        ["full_profit_factor", "min_slice_profit_factor", "full_avg_trade"],
        ascending=[False, False, False],
    )
    top = summary.sort_values(["full_profit_factor", "min_slice_profit_factor"], ascending=[False, False]).head(20)
    best_model_a = summary.loc[summary["model"].eq("protected_entry")].sort_values(
        ["full_profit_factor", "min_slice_profit_factor"],
        ascending=[False, False],
    )
    best_model_b = summary.loc[summary["model"].eq("observe_then_enter")].sort_values(
        ["full_profit_factor", "min_slice_profit_factor"],
        ascending=[False, False],
    )

    lines = [
        "# HYPE-5M-PBTR-V5 Executable Search 2026-06-24",
        "",
        "Family id: `HYPE-5M-PBTR`",
        "",
        "This is the first executable-first V5 search after V3.3/V4 failed live-realistic trailing audits. The search rejects the old hidden lockout model and tests only states that can be placed as real orders.",
        "",
        "## Executable Models",
        "",
        "- `protected_entry`: enter after a closed pullback signal and activate a protective stop immediately.",
        "- `observe_then_enter`: treat the pullback signal as an observation trigger, enter only after confirmation bars, and activate a protective stop immediately after entry.",
        "",
        "Both models use observed live cost assumptions: fee `4.1466 bps/fill`, entry slippage `10.73 bps`, and exit slippage `2.64 bps`. Stop gaps and crossed stops are market exits, never fills at an already-crossed stop price.",
        "",
        "## V5 Gate",
        "",
        "- Full-sample trades `>=500`.",
        "- Full-sample PF `>=1.30`.",
        "- Worst validation-slice PF `>=1.05`.",
        "- Payoff `>=1.20`.",
        "- Average trade after costs `>0`.",
        "- Max drawdown at 1x no worse than `-25%`.",
        "- Profitable months at least `8/14`.",
        "",
        "## Passing Candidates",
        "",
        *render_table(passed, limit=20),
        "",
        "## Watchlist",
        "",
        "Rows here do not pass V5 gate but are positive enough to inspect if no full candidate exists.",
        "",
        *render_table(watch, limit=20),
        "",
        "## Best Overall By PF",
        "",
        *render_table(top, limit=20),
        "",
        "## Best Protected-Entry Rows",
        "",
        *render_table(best_model_a, limit=12),
        "",
        "## Best Observation-Then-Entry Rows",
        "",
        *render_table(best_model_b, limit=12),
        "",
        "## Decision",
        "",
    ]
    if len(passed):
        best = passed.iloc[0]
        lines.extend(
            [
                f"`{best['label']}` is the first V5 candidate to promote for deeper ablation and live-spec drafting. It passes the executable-first gate, but it is not production-approved until full ablation, side diagnostics, and paper-live checks are complete.",
                "",
                "Next steps:",
                "",
                "1. Run full parameter ablation around the passing candidate.",
                "2. Add side-specific diagnostics and monthly/weekly breakdown.",
                "3. Draft a small-notional live spec only if ablation does not break the candidate.",
            ]
        )
    elif len(watch):
        best = watch.iloc[0]
        lines.extend(
            [
                f"No candidate passed the V5 gate. The closest watchlist row is `{best['label']}` with PF `{num(float(best['full_profit_factor']))}`, min-slice PF `{num(float(best['min_slice_profit_factor']))}`, avg trade `{pct(float(best['full_avg_trade']))}`, and max DD `{pct(float(best['full_max_dd']))}`.",
                "",
                "This is not enough for live handoff. The next step should be event-quality modeling or a stricter observation-then-entry search, not loosening the executable gate.",
            ]
        )
    else:
        lines.extend(
            [
                "No row is positive enough for a watchlist. Under executable order semantics, the current pullback-trailing family still does not have a live-tradable edge.",
                "",
                "Recommendation: stop direct rule search and convert pullback events into an event-quality dataset.",
            ]
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            "- Script: `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v5_executable_search.py`",
            f"- JSON: `{REPORT_PATH}`",
            f"- Summary CSV: `{SUMMARY_PATH}`",
            f"- Slice CSV: `{SLICES_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= END_TS].reset_index(drop=True)
    frame = add_features(raw)
    slices = validation_slices(frame)
    month_items = month_slices(frame)
    week_items = weekly_slices(frame)
    configs = build_configs()

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    for idx, cfg in enumerate(configs, start=1):
        summary, rows = evaluate_config(frame, cfg, slices, month_items, week_items)
        summary_rows.append(summary)
        slice_rows.extend(rows)
        if idx % 100 == 0:
            print(f"tested={idx}/{len(configs)}", flush=True)

    summary = pd.DataFrame(summary_rows)
    slices_df = pd.DataFrame(slice_rows)
    summary = summary.sort_values(["passes_v5_gate", "score", "full_profit_factor"], ascending=[False, False, False])

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slices_df.to_csv(SLICES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy_line": "HYPE-5M-PBTR-V5",
                "search": "executable_first_model_a_b",
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                    "net_slippage_rate_on_turnover": NET_SLIPPAGE_RATE_ON_TURNOVER,
                },
                "gates": {
                    "full_trades": 500,
                    "full_profit_factor": 1.30,
                    "min_slice_profit_factor": 1.05,
                    "payoff_ratio": 1.20,
                    "avg_trade": 0.0,
                    "max_dd_at_least": -0.25,
                    "profitable_months": 8,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "slices": str(SLICES_PATH),
                },
                "top_rows": summary.head(80).to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(f"summary={SUMMARY_PATH}")
    print(f"slices={SLICES_PATH}")
    print(
        summary[
            [
                "label",
                "passes_v5_gate",
                "watchlist",
                "full_trades",
                "full_profit_factor",
                "min_slice_profit_factor",
                "full_win_rate",
                "full_payoff_ratio",
                "full_avg_trade",
                "full_max_dd",
                "profitable_months",
            ]
        ]
        .head(30)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
