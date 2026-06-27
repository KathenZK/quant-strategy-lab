from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

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


retry = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v33_retry_arm.py", "hype_pbtr_v33_retry_arm")
v33 = retry.v33

RUN_DATE = "2026-06-27"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_combo_overlay_{RUN_DATE}.json"
PRESCREEN_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_combo_overlay_prescreen_{RUN_DATE}.csv"
FULL_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_combo_overlay_full_{RUN_DATE}.csv"
ROBUST_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_combo_overlay_robust_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_combo_overlay_top_trades_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v3-3-1-combo-overlay-{RUN_DATE}.md"

Mode = Literal["5m_conservative", "5m_optimistic", "1m_conservative", "1m_optimistic"]

EMERGENCY_MULTS = (0.75, 1.0, 1.25)
BREAKEVEN_TRIGGERS = (0.5, 1.0)
LOCK_PROFIT_MULTS = (0.0, 0.25)
TRAIL_START_MULTS = (1.5, 2.0)
TRAIL_DISTANCE_MULTS = (1.0, 1.5)
FAIL_BARS = (3, 5)
FAIL_PROGRESS_MULTS = (0.3, 0.5)
FULL_RECHECK_LIMIT = 60


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def fmt_mult(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.2f}x"


def slug(value: float) -> str:
    return str(value).replace(".", "p")


def add_range10(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["range10"] = (result["high"] - result["low"]).rolling(10, min_periods=10).mean()
    return result


def config_id(config: dict[str, Any]) -> str:
    return (
        f"em{slug(config['emergency_mult'])}"
        f"__be{slug(config['breakeven_trigger'])}"
        f"__lock{slug(config['lock_profit_mult'])}"
        f"__ts{slug(config['trail_start_mult'])}"
        f"__td{slug(config['trail_distance_mult'])}"
        f"__fail{config['fail_bars']}_{slug(config['fail_progress_mult'])}"
    )


def build_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    for emergency_mult in EMERGENCY_MULTS:
        for breakeven_trigger in BREAKEVEN_TRIGGERS:
            for lock_profit_mult in LOCK_PROFIT_MULTS:
                for trail_start_mult in TRAIL_START_MULTS:
                    for trail_distance_mult in TRAIL_DISTANCE_MULTS:
                        for fail_bars in FAIL_BARS:
                            for fail_progress_mult in FAIL_PROGRESS_MULTS:
                                config = {
                                    "emergency_mult": emergency_mult,
                                    "breakeven_trigger": breakeven_trigger,
                                    "lock_profit_mult": lock_profit_mult,
                                    "trail_start_mult": trail_start_mult,
                                    "trail_distance_mult": trail_distance_mult,
                                    "fail_bars": fail_bars,
                                    "fail_progress_mult": fail_progress_mult,
                                }
                                config["config_id"] = config_id(config)
                                configs.append(config)
    return configs


def stop_touched(direction: int, stop_price: float, high_price: float, low_price: float) -> bool:
    return low_price <= stop_price if direction > 0 else high_price >= stop_price


def trigger_touched(direction: int, trigger_price: float, high_price: float, low_price: float) -> bool:
    return high_price >= trigger_price if direction > 0 else low_price <= trigger_price


def tighten_stop(direction: int, current: float, candidate: float) -> float:
    return max(current, candidate) if direction > 0 else min(current, candidate)


def update_trailing_stop(
    direction: int,
    active_stop: float,
    max_favorable: float,
    min_favorable: float,
    distance: float,
) -> float:
    candidate = max_favorable - distance if direction > 0 else min_favorable + distance
    return tighten_stop(direction, active_stop, candidate)


def minute_rows(frame_1m: pd.DataFrame | None, start: pd.Timestamp) -> pd.DataFrame | None:
    if frame_1m is None:
        return None
    rows = frame_1m.loc[(frame_1m["ts"] >= start) & (frame_1m["ts"] < start + pd.Timedelta(minutes=5))]
    return rows if len(rows) else None


def process_interval(
    *,
    direction: int,
    high_price: float,
    low_price: float,
    mode: Mode,
    active_stop: float,
    entry_price: float,
    range_value: float,
    max_favorable: float,
    min_favorable: float,
    breakeven_done: bool,
    trailing_active: bool,
    config: dict[str, Any],
) -> tuple[str | None, float | None, float, float, float, bool, bool]:
    breakeven_price = entry_price + direction * float(config["lock_profit_mult"]) * range_value
    breakeven_trigger = entry_price + direction * float(config["breakeven_trigger"]) * range_value
    trail_start = entry_price + direction * float(config["trail_start_mult"]) * range_value
    trail_distance = float(config["trail_distance_mult"]) * range_value

    def apply_profit_updates(
        stop_price: float,
        max_fav: float,
        min_fav: float,
        be_done: bool,
        trail_on: bool,
    ) -> tuple[float, float, float, bool, bool]:
        max_fav = max(max_fav, high_price)
        min_fav = min(min_fav, low_price)
        if not be_done and trigger_touched(direction, breakeven_trigger, high_price, low_price):
            stop_price = tighten_stop(direction, stop_price, breakeven_price)
            be_done = True
        if trigger_touched(direction, trail_start, high_price, low_price):
            trail_on = True
        if trail_on:
            stop_price = update_trailing_stop(direction, stop_price, max_fav, min_fav, trail_distance)
        return stop_price, max_fav, min_fav, be_done, trail_on

    if mode.endswith("conservative"):
        if stop_touched(direction, active_stop, high_price, low_price):
            return "combo_stop", active_stop, max_favorable, min_favorable, active_stop, breakeven_done, trailing_active
        active_stop, max_favorable, min_favorable, breakeven_done, trailing_active = apply_profit_updates(
            active_stop,
            max_favorable,
            min_favorable,
            breakeven_done,
            trailing_active,
        )
        if stop_touched(direction, active_stop, high_price, low_price):
            return "combo_stop", active_stop, max_favorable, min_favorable, active_stop, breakeven_done, trailing_active
    else:
        active_stop, max_favorable, min_favorable, breakeven_done, trailing_active = apply_profit_updates(
            active_stop,
            max_favorable,
            min_favorable,
            breakeven_done,
            trailing_active,
        )
        if stop_touched(direction, active_stop, high_price, low_price):
            return "combo_stop", active_stop, max_favorable, min_favorable, active_stop, breakeven_done, trailing_active
    return None, None, max_favorable, min_favorable, active_stop, breakeven_done, trailing_active


def simulate_combo(
    frame: pd.DataFrame,
    signal: np.ndarray,
    frame_1m: pd.DataFrame | None,
    mode: Mode,
    config: dict[str, Any],
) -> list[Any]:
    ts = pd.to_datetime(frame["ts"], utc=True)
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    range10 = frame["range10"].to_numpy("float64")
    trades: list[Any] = []
    blocked_until = -1

    for sig_i in np.flatnonzero(signal):
        direction = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= len(frame) or entry_i <= blocked_until or direction == 0:
            continue
        signal_atr = float(atr[sig_i])
        range_value = float(range10[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0 or not np.isfinite(range_value) or range_value <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + direction * v33.ENTRY_SLIPPAGE_RATE))
        active_stop = entry_price - direction * float(config["emergency_mult"]) * range_value
        max_favorable = entry_price
        min_favorable = entry_price
        breakeven_done = False
        trailing_active = False
        reason = "time"
        exit_i = len(frame) - 1
        raw_exit = float(close[-1])

        for j in range(entry_i, len(frame)):
            bars_held = j - entry_i + 1
            if bars_held > int(config["fail_bars"]):
                favorable_distance = (max_favorable - entry_price) if direction > 0 else (entry_price - min_favorable)
                if favorable_distance < float(config["fail_progress_mult"]) * range_value:
                    reason = "early_fail_open"
                    raw_exit = float(open_[j])
                    exit_i = j
                    break

            if mode.startswith("1m_"):
                rows = minute_rows(frame_1m, pd.Timestamp(ts.iloc[j]))
                if rows is None:
                    intervals = [(float(high[j]), float(low[j]))]
                else:
                    intervals = [(float(row.high), float(row.low)) for row in rows.itertuples(index=False)]
            else:
                intervals = [(float(high[j]), float(low[j]))]

            exited = False
            for high_i, low_i in intervals:
                interval_reason, interval_exit, max_favorable, min_favorable, active_stop, breakeven_done, trailing_active = process_interval(
                    direction=direction,
                    high_price=high_i,
                    low_price=low_i,
                    mode=mode,
                    active_stop=active_stop,
                    entry_price=entry_price,
                    range_value=range_value,
                    max_favorable=max_favorable,
                    min_favorable=min_favorable,
                    breakeven_done=breakeven_done,
                    trailing_active=trailing_active,
                    config=config,
                )
                if interval_reason is not None and interval_exit is not None:
                    reason = interval_reason
                    raw_exit = float(interval_exit)
                    exit_i = j
                    exited = True
                    break
            if exited:
                break

        exit_price = retry.exit_price_with_cost(raw_exit, direction)
        net, mae, mfe = retry.net_mae_mfe(direction, entry_price, exit_price, high[entry_i : exit_i + 1], low[entry_i : exit_i + 1])
        trades.append(
            v33.Trade(
                config=str(config["config_id"]),
                signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                reason=reason,
                bars_held=int(exit_i - entry_i + 1),
                net_ret_1x=float(net),
                mae_1x=float(mae),
                mfe_1x=float(mfe),
            )
        )
        blocked_until = exit_i
    return trades


def summarize(config: dict[str, Any], mode: Mode, trades: list[Any], frame: pd.DataFrame) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return {**config, "mode": mode, **v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end)}


def render_markdown(prescreen: pd.DataFrame, full: pd.DataFrame, robust: pd.DataFrame) -> str:
    def rows_table(rows: pd.DataFrame) -> list[str]:
        lines = ["| config | mode | trades | total | win | PF | payoff | max_dd |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for row in rows.to_dict(orient="records"):
            lines.append(
                f"| `{row['config_id']}` | `{row['mode']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
                f"`{fmt_pct(float(row['win_rate']))}` | `{fmt_num(float(row['profit_factor']))}` | "
                f"`{fmt_num(float(row['payoff_ratio']))}` | `{fmt_pct(float(row['max_dd']))}` |"
            )
        return lines

    lines = [
        "# HYPE-5M-PBTR-V3.3.1 combo overlay search 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告把组合式风控 overlay 加到全量 V3.3.1 信号：入场即 emergency stop；达到浮盈阈值后把 stop 推到 entry 附近或小盈利；更高浮盈后启动 range10 trailing；若前几根 K 没有达到最小正向推进则 time exit。",
        "",
        "样本统一裁剪到本地 1m/5m 重叠区间，以便比较 5m/1m 悲观和乐观口径。",
        "",
        "## Prescreen Top 20",
        "",
    ]
    lines.extend(rows_table(prescreen.sort_values(["profit_factor", "total_return"], ascending=False).head(20)))
    lines.extend(["", "## 四口径复核 Top 30", ""])
    lines.extend(rows_table(full.sort_values(["profit_factor", "total_return"], ascending=False).head(30)))
    lines.extend(["", "## Robust", ""])
    if robust.empty:
        lines.append("没有配置完成四口径稳健复核。")
    else:
        lines.append("| config | min_trades | min_total | min_pf | worst_dd |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for row in robust.sort_values(["min_pf", "min_total_return"], ascending=False).head(30).to_dict(orient="records"):
            lines.append(
                f"| `{row['config_id']}` | `{int(row['min_trades'])}` | `{fmt_pct(float(row['min_total_return']))}` | "
                f"`{fmt_num(float(row['min_pf']))}` | `{fmt_pct(float(row['worst_max_dd']))}` |"
            )
    if robust.empty:
        conclusion = "没有稳健配置。"
    else:
        best = robust.sort_values(["min_pf", "min_total_return"], ascending=False).iloc[0]
        conclusion = (
            f"四口径最佳为 `{best['config_id']}`：min trades `{int(best['min_trades'])}`，"
            f"min total `{fmt_pct(float(best['min_total_return']))}`，min PF `{fmt_num(float(best['min_pf']))}`，"
            f"worst max drawdown `{fmt_pct(float(best['worst_max_dd']))}`。"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            conclusion,
            "",
            "若 robust 最佳仍低于 PF 1，说明这套全量 V3.3.1 组合 overlay 不能救活；若 PF>1 但交易仍大幅亏损或回撤过深，需要继续做切片和 OOS 复核。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- JSON：`{REPORT_PATH}`",
            f"- prescreen CSV：`{PRESCREEN_PATH}`",
            f"- full CSV：`{FULL_PATH}`",
            f"- robust CSV：`{ROBUST_PATH}`",
            f"- top trades CSV：`{TRADES_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw_5m = v33.load_all_hype_5m()
    frame_1m = retry.load_hype_1m()
    if frame_1m is not None:
        min_ts = max(pd.Timestamp(raw_5m["ts"].iloc[0]), pd.Timestamp(frame_1m["ts"].iloc[0]).ceil("5min"))
        max_ts = min(pd.Timestamp(raw_5m["ts"].iloc[-1]), pd.Timestamp(frame_1m["ts"].iloc[-1]).floor("5min"))
        raw_5m = raw_5m.loc[(raw_5m["ts"] >= min_ts) & (raw_5m["ts"] <= max_ts)].reset_index(drop=True)
        frame_1m = frame_1m.loc[
            (frame_1m["ts"] >= raw_5m["ts"].iloc[0]) & (frame_1m["ts"] <= max_ts + pd.Timedelta(minutes=5))
        ].reset_index(drop=True)

    frame = add_range10(v33.add_minimal_features(raw_5m, v33.V33_CONFIG))
    signal = v33.build_v33_signal(frame, v33.V33_CONFIG)
    configs = build_configs()
    prescreen_rows: list[dict[str, Any]] = []
    for config in configs:
        trades = simulate_combo(frame, signal, frame_1m, "5m_conservative", config)
        prescreen_rows.append(summarize(config, "5m_conservative", trades, frame))

    prescreen = pd.DataFrame(prescreen_rows)
    selected = prescreen.sort_values(["profit_factor", "total_return"], ascending=False).head(FULL_RECHECK_LIMIT)
    selected_ids = set(selected["config_id"].tolist())
    modes: list[Mode] = ["5m_conservative", "5m_optimistic"]
    if frame_1m is not None:
        modes.extend(["1m_conservative", "1m_optimistic"])

    full_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    for config in configs:
        if config["config_id"] not in selected_ids:
            continue
        for mode in modes:
            trades = simulate_combo(frame, signal, frame_1m, mode, config)
            full_rows.append(summarize(config, mode, trades, frame))
            if mode == "5m_conservative":
                for i, trade in enumerate(trades[:100], start=1):
                    trade_rows.append(
                        {
                            "config_id": config["config_id"],
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
                            "mae_1x": trade.mae_1x,
                            "mfe_1x": trade.mfe_1x,
                        }
                    )

    full = pd.DataFrame(full_rows)
    robust = (
        full.groupby("config_id")
        .agg(
            modes=("mode", "nunique"),
            min_trades=("trades", "min"),
            min_pf=("profit_factor", "min"),
            min_total_return=("total_return", "min"),
            worst_max_dd=("max_dd", "min"),
            avg_trades=("trades", "mean"),
        )
        .reset_index()
    )
    robust = robust.loc[robust["modes"].eq(len(modes))].reset_index(drop=True)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    prescreen.to_csv(PRESCREEN_PATH, index=False)
    full.to_csv(FULL_PATH, index=False)
    robust.to_csv(ROBUST_PATH, index=False)
    pd.DataFrame(trade_rows).to_csv(TRADES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(prescreen, full, robust), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V3.3.1",
                "audit": "combo_overlay_search",
                "definition": {
                    "base": asdict(v33.V33_CONFIG),
                    "emergency_mults": list(EMERGENCY_MULTS),
                    "breakeven_triggers": list(BREAKEVEN_TRIGGERS),
                    "lock_profit_mults": list(LOCK_PROFIT_MULTS),
                    "trail_start_mults": list(TRAIL_START_MULTS),
                    "trail_distance_mults": list(TRAIL_DISTANCE_MULTS),
                    "fail_bars": list(FAIL_BARS),
                    "fail_progress_mults": list(FAIL_PROGRESS_MULTS),
                    "full_recheck_limit": FULL_RECHECK_LIMIT,
                    "used_1m": frame_1m is not None,
                    "data_start": str(frame["ts"].iloc[0]),
                    "data_end": str(frame["ts"].iloc[-1]),
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "prescreen": str(PRESCREEN_PATH),
                    "full": str(FULL_PATH),
                    "robust": str(ROBUST_PATH),
                    "top_trades": str(TRADES_PATH),
                },
                "best_robust": robust.sort_values(["min_pf", "min_total_return"], ascending=False)
                .head(30)
                .to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(robust.sort_values(["min_pf", "min_total_return"], ascending=False).head(30).to_string(index=False))


if __name__ == "__main__":
    main()
