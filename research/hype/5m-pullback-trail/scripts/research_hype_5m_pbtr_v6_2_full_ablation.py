from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v6 = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v6_live_executable_search.py", "hype_pbtr_v6_search_for_v62")

RUN_DATE = "2026-06-28"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
ABLATION_ROOT = FAMILY_ROOT / "ablations"

SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2_full_ablation_summary_{RUN_DATE}.csv"
SLICE_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2_full_ablation_slices_{RUN_DATE}.csv"
SIDE_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2_full_ablation_sides_{RUN_DATE}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2_full_ablation_monthly_{RUN_DATE}.csv"
TRADE_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2_baseline_trades_{RUN_DATE}.csv"
JSON_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2_full_ablation_{RUN_DATE}.json"
MARKDOWN_PATH = ABLATION_ROOT / f"hype-5m-pbtr-v6-2-full-parameter-ablation-{RUN_DATE}.md"


@dataclass(frozen=True, slots=True)
class LegConfig:
    enabled: bool
    side: str
    ema_fast: int
    ema_slow: int
    pullback_buffer: float
    require_candle: bool
    htf_threshold: float | None
    quality_window: int | None
    quality_threshold: float | None
    tp_atr: float
    sl_atr: float
    trail_atr: float
    time_exit_bars: int


@dataclass(frozen=True, slots=True)
class V62Config:
    name: str = "HYPE-5M-PBTR-V6.2"
    long: LegConfig = LegConfig(
        enabled=True,
        side="long",
        ema_fast=21,
        ema_slow=55,
        pullback_buffer=0.01,
        require_candle=False,
        htf_threshold=0.5,
        quality_window=192,
        quality_threshold=788.123,
        tp_atr=2.5,
        sl_atr=7.0,
        trail_atr=0.0,
        time_exit_bars=36,
    )
    short: LegConfig = LegConfig(
        enabled=True,
        side="short",
        ema_fast=34,
        ema_slow=144,
        pullback_buffer=0.0,
        require_candle=False,
        htf_threshold=None,
        quality_window=48,
        quality_threshold=400.0,
        tp_atr=1.5,
        sl_atr=2.0,
        trail_atr=0.0,
        time_exit_bars=48,
    )
    priority: str = "long_first"
    leverage: float = 3.0


BASELINE = V62Config()


def fmt_pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def fmt_num(value: float, digits: int = 3) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def label_value(value: Any) -> str:
    return str(value).replace(".", "p").replace("-", "neg").replace("/", "_").replace(" ", "")


def side_to_int(side: str) -> int:
    if side == "long":
        return 1
    if side == "short":
        return -1
    raise ValueError(side)


def signal_spec(leg: LegConfig) -> Any:
    return v6.SignalSpec(
        style="pullback_reclaim",
        ema_fast=leg.ema_fast,
        ema_slow=leg.ema_slow,
        pullback_buffer=leg.pullback_buffer,
        side_mode=leg.side,
        require_candle=leg.require_candle,
        htf_threshold=leg.htf_threshold,
    )


def exit_spec(leg: LegConfig) -> Any:
    return v6.ExitSpec(
        tp_atr=leg.tp_atr,
        sl_atr=leg.sl_atr,
        trail_atr=leg.trail_atr,
        time_exit_bars=leg.time_exit_bars,
    )


def quality_label(leg: LegConfig) -> str:
    if leg.quality_window is None or leg.quality_threshold is None:
        return "none"
    return f"dir_ret{leg.quality_window}_bps>={leg.quality_threshold:g}"


def build_leg_signal(frame: pd.DataFrame, leg: LegConfig) -> tuple[np.ndarray, int, int]:
    if not leg.enabled:
        return np.zeros(len(frame), dtype=np.int8), 0, 0
    spec = signal_spec(leg)
    raw_signal = v6.build_signal(frame, spec)
    raw_count = int(np.count_nonzero(raw_signal))
    if leg.quality_window is None or leg.quality_threshold is None:
        return raw_signal, raw_count, raw_count
    events = v6.event_features(frame, raw_signal, spec)
    column = f"dir_ret{leg.quality_window}_bps"
    keep = np.isfinite(events[column].to_numpy("float64")) & (
        events[column].to_numpy("float64") >= float(leg.quality_threshold)
    )
    filtered = v6.filtered_signal(raw_signal, events, keep)
    return filtered, raw_count, int(np.count_nonzero(filtered))


def equity_metrics(returns: np.ndarray) -> dict[str, float]:
    equity = np.cumprod(1.0 + returns)
    equity_with_start = np.r_[1.0, equity]
    peak = np.maximum.accumulate(equity_with_start)
    dd = equity_with_start / peak - 1.0
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    return {
        "trades": float(len(returns)),
        "total_return": float(equity[-1] - 1.0) if len(equity) else 0.0,
        "max_dd": float(dd.min()) if len(dd) else 0.0,
        "avg_trade": float(returns.mean()) if len(returns) else 0.0,
        "win_rate": float((returns > 0).mean()) if len(returns) else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else np.inf,
        "payoff_ratio": float(wins.mean() / -losses.mean()) if len(wins) and len(losses) else np.inf,
        "worst_trade": float(returns.min()) if len(returns) else 0.0,
        "best_trade": float(returns.max()) if len(returns) else 0.0,
    }


def metrics_for_trades(trades: list[Any], leverage: float, *, start: pd.Timestamp | None = None, end: pd.Timestamp | None = None) -> dict[str, float]:
    selected = trades
    if start is not None:
        selected = [trade for trade in selected if trade.entry_ts >= start]
    if end is not None:
        selected = [trade for trade in selected if trade.entry_ts < end]
    returns = np.array([trade.net_ret_1x * leverage for trade in selected], dtype="float64")
    return equity_metrics(returns)


def simulate_one(frame: pd.DataFrame, sig_i: int, side: int, leg: LegConfig, label: str) -> tuple[Any | None, int]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    entry_i = sig_i + 1
    n = len(frame)
    if side == 0 or entry_i >= n:
        return None, sig_i
    signal_atr = float(atr[sig_i])
    if not np.isfinite(signal_atr) or signal_atr <= 0:
        return None, sig_i

    entry_price = float(open_[entry_i] * (1.0 + side * v6.ENTRY_SLIPPAGE_RATE))
    target_price = entry_price + side * leg.tp_atr * signal_atr
    active_stop = entry_price - side * leg.sl_atr * signal_atr
    exit_i = min(n - 1, entry_i + leg.time_exit_bars)
    raw_exit_price = float(open_[exit_i] if exit_i < n else close[-1])
    reason = "time_open"
    peak = entry_price
    trough = entry_price
    for bar_i in range(entry_i, min(n, entry_i + leg.time_exit_bars + 1)):
        if v6.crossed_stop(float(open_[bar_i]), active_stop, side):
            exit_i = bar_i
            raw_exit_price = float(open_[bar_i])
            reason = "stop_gap_open"
            break
        if v6.crossed_target(float(open_[bar_i]), target_price, side):
            exit_i = bar_i
            raw_exit_price = float(target_price)
            reason = "target_gap_or_open"
            break
        if bar_i == entry_i + leg.time_exit_bars:
            exit_i = bar_i
            raw_exit_price = float(open_[bar_i])
            reason = "time_open"
            break
        stop_hit = v6.touched_stop(float(high[bar_i]), float(low[bar_i]), active_stop, side)
        target_hit = v6.touched_target(float(high[bar_i]), float(low[bar_i]), target_price, side)
        if stop_hit and target_hit:
            exit_i = bar_i
            raw_exit_price = float(active_stop)
            reason = "both_hit_stop_first"
            break
        if stop_hit:
            exit_i = bar_i
            raw_exit_price = float(active_stop)
            reason = "stop_market"
            break
        if target_hit:
            exit_i = bar_i
            raw_exit_price = float(target_price)
            reason = "target"
            break
        if side > 0:
            peak = max(peak, float(high[bar_i]))
            if leg.trail_atr > 0 and np.isfinite(atr[bar_i]):
                active_stop = max(active_stop, peak - leg.trail_atr * float(atr[bar_i]))
        else:
            trough = min(trough, float(low[bar_i]))
            if leg.trail_atr > 0 and np.isfinite(atr[bar_i]):
                active_stop = min(active_stop, trough + leg.trail_atr * float(atr[bar_i]))

    path_high = high[entry_i : exit_i + 1]
    path_low = low[entry_i : exit_i + 1]
    if side > 0:
        mae = float(np.nanmin(path_low / entry_price - 1.0))
        mfe = float(np.nanmax(path_high / entry_price - 1.0))
    else:
        mae = float(np.nanmin(side * (path_high / entry_price - 1.0)))
        mfe = float(np.nanmax(side * (path_low / entry_price - 1.0)))
    exit_price = v6.exit_price_with_cost(raw_exit_price, side)
    gross = side * (exit_price / entry_price - 1.0)
    fee_cost = v6.FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
    net = gross - fee_cost
    return (
        v6.Trade(
            config=label,
            signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
            entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
            exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
            side=side,
            entry_price=entry_price,
            exit_price=exit_price,
            reason=reason,
            bars_held=int(exit_i - entry_i + 1),
            net_ret_1x=float(net),
            mae_1x=float(mae - v6.FEE_RATE_PER_FILL),
            mfe_1x=float(mfe),
        ),
        exit_i,
    )


def simulate_combo(
    frame: pd.DataFrame,
    long_signal: np.ndarray,
    short_signal: np.ndarray,
    cfg: V62Config,
    label: str,
) -> tuple[list[Any], dict[str, int]]:
    priority_order = {"long": 0, "short": 1} if cfg.priority == "long_first" else {"short": 0, "long": 1}
    events: list[tuple[int, str, int, LegConfig]] = []
    if cfg.long.enabled:
        events.extend((int(i), "long", int(long_signal[i]), cfg.long) for i in np.flatnonzero(long_signal))
    if cfg.short.enabled:
        events.extend((int(i), "short", int(short_signal[i]), cfg.short) for i in np.flatnonzero(short_signal))
    events.sort(key=lambda item: (item[0], priority_order[item[1]]))
    long_idx = set(int(i) for i in np.flatnonzero(long_signal))
    short_idx = set(int(i) for i in np.flatnonzero(short_signal))
    stats = {
        "long_signal_count": len(long_idx),
        "short_signal_count": len(short_idx),
        "same_bar_signal_count": len(long_idx & short_idx),
        "accepted_long": 0,
        "accepted_short": 0,
        "blocked_long": 0,
        "blocked_short": 0,
    }
    blocked_until = -1
    trades: list[Any] = []
    for sig_i, source, side, leg in events:
        entry_i = sig_i + 1
        if entry_i <= blocked_until:
            stats[f"blocked_{source}"] += 1
            continue
        trade, exit_i = simulate_one(frame, sig_i, side, leg, f"{label}_{source}")
        if trade is None:
            continue
        trades.append(trade)
        stats[f"accepted_{source}"] += 1
        blocked_until = exit_i
    return trades, stats


def reason_counts(trades: list[Any]) -> str:
    counts: dict[str, int] = {}
    for trade in trades:
        counts[trade.reason] = counts.get(trade.reason, 0) + 1
    return json.dumps(counts, ensure_ascii=False, sort_keys=True)


def robust_pass(row: dict[str, Any]) -> bool:
    return bool(
        row["trades"] >= 150
        and row["profit_factor"] >= 1.3
        and row["avg_trade"] > 0.0
        and row["max_dd"] > -0.35
        and row["is_profit_factor"] >= 1.1
        and row["val_profit_factor"] >= 1.0
        and row["oos_trades"] >= 10
        and row["oos_profit_factor"] >= 1.0
        and row["short_trades"] >= 30
        and row["short_profit_factor"] >= 1.1
        and row["short_oos_trades"] >= 5
        and row["worst_trade"] > -0.25
    )


def validation_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return [
        {"name": "is", "start": start, "end": v6.IS_END},
        {"name": "val", "start": v6.IS_END, "end": v6.VAL_END},
        {"name": "oos", "start": v6.VAL_END, "end": end},
    ]


def side_metrics(trades: list[Any], cfg: V62Config, side: int) -> dict[str, float]:
    return metrics_for_trades([trade for trade in trades if trade.side == side], cfg.leverage)


def evaluate_variant(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[Any]]:
    cfg: V62Config = spec["cfg"]
    long_signal, long_raw, long_filtered = build_leg_signal(frame, cfg.long)
    short_signal, short_raw, short_filtered = build_leg_signal(frame, cfg.short)
    trades, exec_stats = simulate_combo(frame, long_signal, short_signal, cfg, str(spec["label"]))
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    row: dict[str, Any] = {
        "label": spec["label"],
        "family": spec["family"],
        "parameter": spec["parameter"],
        "value": spec["value"],
        "config_json": json.dumps(asdict(cfg), ensure_ascii=False, sort_keys=True),
        "long_raw_signal_count": long_raw,
        "long_filtered_signal_count": long_filtered,
        "short_raw_signal_count": short_raw,
        "short_filtered_signal_count": short_filtered,
        "reason_counts": reason_counts(trades),
        **exec_stats,
        **metrics_for_trades(trades, cfg.leverage, start=start, end=end),
    }
    for item in validation_slices(frame):
        metrics = metrics_for_trades(trades, cfg.leverage, start=item["start"], end=item["end"])
        for key, value in metrics.items():
            row[f"{item['name']}_{key}"] = value

    long_metrics = side_metrics(trades, cfg, 1)
    short_metrics = side_metrics(trades, cfg, -1)
    for key, value in long_metrics.items():
        row[f"long_{key}"] = value
    for key, value in short_metrics.items():
        row[f"short_{key}"] = value
    short_oos = metrics_for_trades(
        [trade for trade in trades if trade.side < 0],
        cfg.leverage,
        start=v6.VAL_END,
        end=end,
    )
    row["short_oos_trades"] = short_oos["trades"]
    row["short_oos_profit_factor"] = short_oos["profit_factor"]
    row["robust_pass"] = robust_pass(row)

    slice_rows = []
    for item in validation_slices(frame):
        slice_rows.append(
            {
                "label": spec["label"],
                "slice": item["name"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metrics_for_trades(trades, cfg.leverage, start=item["start"], end=item["end"]),
            }
        )
    side_rows = []
    for side, side_label in ((1, "long"), (-1, "short")):
        side_trades = [trade for trade in trades if trade.side == side]
        side_rows.append({"label": spec["label"], "side": side_label, **metrics_for_trades(side_trades, cfg.leverage)})
    monthly_rows = []
    for item in v6.month_slices(frame):
        monthly_rows.append(
            {
                "label": spec["label"],
                "month": item["name"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metrics_for_trades(trades, cfg.leverage, start=item["start"], end=item["end"]),
            }
        )
    return row, slice_rows, side_rows, monthly_rows, trades


def replace_leg(cfg: V62Config, leg_name: str, **changes: Any) -> V62Config:
    leg = getattr(cfg, leg_name)
    return replace(cfg, **{leg_name: replace(leg, **changes)})


def build_variants() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = [
        {"label": "baseline_v6_2", "family": "baseline", "parameter": "baseline", "value": "V6.2", "cfg": BASELINE}
    ]

    def add(label: str, family: str, parameter: str, value: Any, cfg: V62Config) -> None:
        variants.append({"label": label, "family": family, "parameter": parameter, "value": value, "cfg": cfg})

    def add_leg(leg_name: str, parameter: str, value: Any, *, family: str, **changes: Any) -> None:
        add(
            f"{leg_name}_{parameter}_{label_value(value)}",
            family,
            f"{leg_name}_{parameter}",
            value,
            replace_leg(BASELINE, leg_name, **changes),
        )

    for fast, slow in ((13, 55), (21, 96), (34, 144), (9, 55)):
        add_leg("long", "ema_pair", f"{fast}/{slow}", family="long_entry", ema_fast=fast, ema_slow=slow)
    for value in (0.0, 0.005, 0.015, 0.02):
        add_leg("long", "pullback_buffer", value, family="long_entry", pullback_buffer=value)
    add_leg("long", "require_candle", True, family="long_entry", require_candle=True)
    for value in (None, 0.0, 0.25, 0.75, 1.0):
        add_leg("long", "htf_threshold", value, family="long_filter", htf_threshold=value)
    for value in (48, 96, 384):
        add_leg("long", "quality_window", value, family="long_filter", quality_window=value)
    for value in (500.0, 600.0, 700.0, 850.0, 1000.0):
        add_leg("long", "quality_threshold", value, family="long_filter", quality_threshold=value)
    for value in (2.0, 3.0, 4.0):
        add_leg("long", "tp_atr", value, family="long_exit", tp_atr=value)
    for value in (4.0, 5.0, 6.0, 8.0, 10.0):
        add_leg("long", "sl_atr", value, family="long_exit", sl_atr=value)
    for value in (12, 24, 48, 72):
        add_leg("long", "time_exit_bars", value, family="long_exit", time_exit_bars=value)

    for fast, slow in ((21, 55), (21, 96), (13, 55), (9, 96)):
        add_leg("short", "ema_pair", f"{fast}/{slow}", family="short_entry", ema_fast=fast, ema_slow=slow)
    for value in (0.005, 0.01, 0.015, 0.02):
        add_leg("short", "pullback_buffer", value, family="short_entry", pullback_buffer=value)
    add_leg("short", "require_candle", True, family="short_entry", require_candle=True)
    for value in (0.0, 0.5, 1.0):
        add_leg("short", "htf_threshold", value, family="short_filter", htf_threshold=value)
    for value in (24, 96, 192):
        add_leg("short", "quality_window", value, family="short_filter", quality_window=value)
    for value in (200.0, 300.0, 500.0, 600.0):
        add_leg("short", "quality_threshold", value, family="short_filter", quality_threshold=value)
    for value in (1.0, 2.0, 2.5, 3.0):
        add_leg("short", "tp_atr", value, family="short_exit", tp_atr=value)
    for value in (1.5, 2.5, 3.0, 4.0):
        add_leg("short", "sl_atr", value, family="short_exit", sl_atr=value)
    for value in (12, 24, 36, 72):
        add_leg("short", "time_exit_bars", value, family="short_exit", time_exit_bars=value)
    for value in (1.0, 1.5, 2.0):
        add_leg("short", "trail_atr", value, family="short_exit", trail_atr=value)

    add("long_only_v6_1", "combo", "enabled_legs", "long_only", replace(BASELINE, short=replace(BASELINE.short, enabled=False)))
    add("short_only_rank2", "combo", "enabled_legs", "short_only", replace(BASELINE, long=replace(BASELINE.long, enabled=False)))
    add("priority_short_first", "combo", "priority", "short_first", replace(BASELINE, priority="short_first"))
    for value in (1.0, 2.0, 4.0):
        add(f"leverage_{label_value(value)}", "sizing", "leverage", value, replace(BASELINE, leverage=value))
    return variants


def table(rows: pd.DataFrame, limit: int = 20) -> list[str]:
    lines = [
        "| 变体 | 参数 | 值 | 交易数 | 总收益 | PF | 平均 | 胜率 | payoff | DD | IS PF | VAL PF | OOS 笔 | OOS PF | short 笔 | short PF | pass |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['parameter']}` | `{row['value']}` | `{int(row['trades'])}` | "
            f"`{fmt_pct(float(row['total_return']))}` | `{fmt_num(float(row['profit_factor']))}` | "
            f"`{fmt_pct(float(row['avg_trade']))}` | `{fmt_pct(float(row['win_rate']))}` | "
            f"`{fmt_num(float(row['payoff_ratio']))}` | `{fmt_pct(float(row['max_dd']))}` | "
            f"`{fmt_num(float(row['is_profit_factor']))}` | `{fmt_num(float(row['val_profit_factor']))}` | "
            f"`{int(row['oos_trades'])}` | `{fmt_num(float(row['oos_profit_factor']))}` | "
            f"`{int(row['short_trades'])}` | `{fmt_num(float(row['short_profit_factor']))}` | `{bool(row['robust_pass'])}` |"
        )
    return lines


def render_markdown(summary: pd.DataFrame, slices: pd.DataFrame, sides: pd.DataFrame, monthly: pd.DataFrame) -> str:
    baseline = summary.loc[summary["label"].eq("baseline_v6_2")].iloc[0]
    variants = summary.loc[~summary["label"].eq("baseline_v6_2")].copy()
    variants["delta_return"] = variants["total_return"] - float(baseline["total_return"])
    variants["delta_dd"] = variants["max_dd"] - float(baseline["max_dd"])
    good = variants.loc[variants["robust_pass"]].sort_values(["total_return", "max_dd"], ascending=[False, False])
    bad = variants.sort_values(["delta_return", "profit_factor"], ascending=[True, True])
    base_sides = sides.loc[sides["label"].eq("baseline_v6_2")]
    base_slices = slices.loc[slices["label"].eq("baseline_v6_2")]
    base_monthly = monthly.loc[monthly["label"].eq("baseline_v6_2")]
    worst_month = base_monthly.sort_values("total_return").iloc[0]
    best_month = base_monthly.sort_values("total_return", ascending=False).iloc[0]
    lines = [
        "# HYPE-5M-PBTR-V6.2 全参数消融 2026-06-28",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "`HYPE-5M-PBTR-V6.2` 正式采用此前 `combo_short_rank2`：V6.1 long-only 加 short-only rank2，组合层严格单仓，同一信号 K 同时出现多空时默认 long 优先。",
        "",
        "## V6.2 Baseline",
        "",
        "| 交易数 | 总收益 | PF | 平均每笔 | 胜率 | payoff | 最大回撤 | 最差单笔 | 最好单笔 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| `{int(baseline['trades'])}` | `{fmt_pct(float(baseline['total_return']))}` | "
            f"`{fmt_num(float(baseline['profit_factor']))}` | `{fmt_pct(float(baseline['avg_trade']))}` | "
            f"`{fmt_pct(float(baseline['win_rate']))}` | `{fmt_num(float(baseline['payoff_ratio']))}` | "
            f"`{fmt_pct(float(baseline['max_dd']))}` | `{fmt_pct(float(baseline['worst_trade']))}` | "
            f"`{fmt_pct(float(baseline['best_trade']))}` |"
        ),
        "",
        "Baseline 参数：",
        "",
        "```text",
        "long: EMA21/55, pullback_buffer=0.01, htf_threshold=0.5, dir_ret192_bps>=788.123, TP=2.5ATR, SL=7ATR, timeout=36",
        "short: EMA34/144, pullback_buffer=0.0, htf_threshold=None, dir_ret48_bps>=400, TP=1.5ATR, SL=2ATR, timeout=48",
        "combo: one-position-only, long_first on same signal bar, fixed 3x",
        "```",
        "",
        "## Side / Slice",
        "",
        "| side | trades | total | DD | PF | avg | win | worst | best |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in base_sides.to_dict(orient="records"):
        lines.append(
            f"| `{row['side']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
            f"`{fmt_pct(float(row['max_dd']))}` | `{fmt_num(float(row['profit_factor']))}` | "
            f"`{fmt_pct(float(row['avg_trade']))}` | `{fmt_pct(float(row['win_rate']))}` | "
            f"`{fmt_pct(float(row['worst_trade']))}` | `{fmt_pct(float(row['best_trade']))}` |"
        )
    lines.extend(["", "| slice | trades | total | DD | PF | avg |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for row in base_slices.to_dict(orient="records"):
        lines.append(
            f"| `{row['slice']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
            f"`{fmt_pct(float(row['max_dd']))}` | `{fmt_num(float(row['profit_factor']))}` | "
            f"`{fmt_pct(float(row['avg_trade']))}` |"
        )
    lines.extend(
        [
            "",
            "## Robust Pass Top",
            "",
            *table(good, limit=20),
            "",
            "## Worst Regressions",
            "",
            *table(bad, limit=20),
            "",
            "## Live Feasibility Notes",
            "",
            f"- 最差月份：`{worst_month['month']}`，总收益 `{fmt_pct(float(worst_month['total_return']))}`，PF `{fmt_num(float(worst_month['profit_factor']))}`。",
            f"- 最好月份：`{best_month['month']}`，总收益 `{fmt_pct(float(best_month['total_return']))}`，PF `{fmt_num(float(best_month['profit_factor']))}`。",
            f"- 退出分布：`{baseline['reason_counts']}`。",
            f"- 同根多空原始冲突：`{int(baseline['same_bar_signal_count'])}`；被持仓阻塞的 long/short 信号分别为 `{int(baseline['blocked_long'])}` / `{int(baseline['blocked_short'])}`。",
            "",
            "V6.2 没有旧 V3/V4 的 delayed trailing stop 穿越问题：入场后立即存在固定 TP/SL，回测对开盘穿越 stop 使用开盘价退出，同根 TP/SL 同时触达按 stop first。小额实盘的主要风险变成 bracket 订单维护、reduce-only 取消一致性、滑点/跳空、以及 short leg 样本偏少。",
            "",
            "## 结论",
            "",
            "本轮将 `combo_short_rank2` 记录为 V6.2 是合理的研究升级，但它仍是 paper/live-dry-run 候选，不是生产 sizing。若小额实盘，应从 fixed 1x 或极小 notional 开始，先验证 30-50 笔订单的信号复现、TP/SL 下单与取消、真实滑点和 timeout 平仓偏差。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- summary：`{SUMMARY_PATH}`",
            f"- slices：`{SLICE_PATH}`",
            f"- sides：`{SIDE_PATH}`",
            f"- monthly：`{MONTHLY_PATH}`",
            f"- baseline trades：`{TRADE_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def trade_rows(trades: list[Any], leverage: float) -> list[dict[str, Any]]:
    rows = []
    for i, trade in enumerate(trades, start=1):
        rows.append(
            {
                "trade_no": i,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": trade.side,
                "reason": trade.reason,
                "bars_held": trade.bars_held,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "net_ret_1x": trade.net_ret_1x,
                "net_ret_levered": trade.net_ret_1x * leverage,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
            }
        )
    return rows


def main() -> None:
    raw = v6.load_closed_frame()
    frame = v6.add_search_features(v6.add_features(raw))
    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    side_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    baseline_trades: list[Any] = []
    for spec in build_variants():
        row, slices, sides, monthly, trades = evaluate_variant(frame, spec)
        summary_rows.append(row)
        slice_rows.extend(slices)
        side_rows.extend(sides)
        monthly_rows.extend(monthly)
        if spec["label"] == "baseline_v6_2":
            baseline_trades = trades
    summary = pd.DataFrame(summary_rows)
    baseline_return = float(summary.loc[summary["label"].eq("baseline_v6_2"), "total_return"].iloc[0])
    summary["delta_total_return"] = summary["total_return"] - baseline_return
    summary = summary.sort_values(["robust_pass", "total_return", "max_dd"], ascending=[False, False, False]).reset_index(drop=True)
    slices = pd.DataFrame(slice_rows)
    sides = pd.DataFrame(side_rows)
    monthly = pd.DataFrame(monthly_rows)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    ABLATION_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slices.to_csv(SLICE_PATH, index=False)
    sides.to_csv(SIDE_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    pd.DataFrame(trade_rows(baseline_trades, BASELINE.leverage)).to_csv(TRADE_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, slices, sides, monthly), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V6.2",
                "baseline": asdict(BASELINE),
                "top": summary.head(30).to_dict(orient="records"),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "slices": str(SLICE_PATH),
                    "sides": str(SIDE_PATH),
                    "monthly": str(MONTHLY_PATH),
                    "baseline_trades": str(TRADE_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
