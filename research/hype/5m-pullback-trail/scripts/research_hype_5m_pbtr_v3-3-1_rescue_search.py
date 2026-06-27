from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, replace
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
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_rescue_search_{RUN_DATE}.json"
PRESCREEN_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_rescue_prescreen_{RUN_DATE}.csv"
FULL_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_rescue_full_{RUN_DATE}.csv"
ROBUST_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_rescue_robust_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_rescue_top_trades_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v3-3-1-rescue-search-{RUN_DATE}.md"

Mode = Literal["5m_conservative", "5m_optimistic", "1m_conservative", "1m_optimistic"]
SideMode = Literal["both", "long", "short"]

PULLBACK_BUFFERS = (-0.0125, -0.01, -0.0075, -0.005)
ARM_DEADLINES = (9,)
MAX_HOLDS: tuple[int | None, ...] = (None, 36)
FULL_RECHECK_LIMIT = 60


@dataclass(frozen=True, slots=True)
class FilterSpec:
    name: str
    min_dir_ret192_bps: float | None = None
    max_spread_bps: float | None = None
    max_adverse_wick_atr: float | None = None
    min_close_pos: float | None = None


FILTERS = (
    FilterSpec("none"),
    FilterSpec("ret192_ge_250", min_dir_ret192_bps=250),
    FilterSpec("ret192_ge_500", min_dir_ret192_bps=500),
    FilterSpec("spread_le_125", max_spread_bps=125),
    FilterSpec("spread_le_200", max_spread_bps=200),
    FilterSpec("adverse_wick_le_0p25", max_adverse_wick_atr=0.25),
    FilterSpec("close_pos_ge_0p6", min_close_pos=0.6),
    FilterSpec("ret250_spread200", min_dir_ret192_bps=250, max_spread_bps=200),
    FilterSpec("ret500_wick0p25", min_dir_ret192_bps=500, max_adverse_wick_atr=0.25),
    FilterSpec("spread125_wick0p25", max_spread_bps=125, max_adverse_wick_atr=0.25),
    FilterSpec("ret250_spread200_close0p6", min_dir_ret192_bps=250, max_spread_bps=200, min_close_pos=0.6),
    FilterSpec("ret500_spread125_wick0p25", min_dir_ret192_bps=500, max_spread_bps=125, max_adverse_wick_atr=0.25),
    FilterSpec("close0p75_wick0p25", min_close_pos=0.75, max_adverse_wick_atr=0.25),
)


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def fmt_mult(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.2f}x"


def slug_float(value: float) -> str:
    return f"{value:+.4f}".replace("+", "p").replace("-", "m").replace(".", "p")


def trailed_stop_without_initial_floor(
    direction: int,
    entry_price: float,
    high_history: np.ndarray,
    low_history: np.ndarray,
    atr_value: float,
    previous: float | None,
) -> float:
    if direction > 0:
        peak = max(entry_price, float(np.nanmax(high_history)))
        candidate = peak - v33.V33_CONFIG.trail_atr * atr_value
        return float(candidate if previous is None else max(previous, candidate))
    trough = min(entry_price, float(np.nanmin(low_history)))
    candidate = trough + v33.V33_CONFIG.trail_atr * atr_value
    return float(candidate if previous is None else min(previous, candidate))


def add_filter_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"]
    open_ = result["open"]
    high = result["high"]
    low = result["low"]
    atr = result["atr14"].replace(0, np.nan)
    candle_range = (high - low).replace(0, np.nan)
    result["ret192_bps"] = (close / close.shift(192) - 1.0) * 10000.0
    result["spread_bps"] = ((result["ema21"] - result["ema96"]).abs() / close) * 10000.0
    result["lower_wick_atr"] = (np.minimum(open_, close) - low) / atr
    result["upper_wick_atr"] = (high - np.maximum(open_, close)) / atr
    result["long_close_pos"] = (close - low) / candle_range
    result["short_close_pos"] = (high - close) / candle_range
    return result


def apply_filters(signal: np.ndarray, frame: pd.DataFrame, side_mode: SideMode, spec: FilterSpec) -> np.ndarray:
    filtered = signal.copy()
    direction = filtered.astype("float64")
    mask = filtered != 0
    if side_mode == "long":
        mask &= filtered > 0
    elif side_mode == "short":
        mask &= filtered < 0
    if spec.min_dir_ret192_bps is not None:
        dir_ret = direction * frame["ret192_bps"].to_numpy("float64")
        mask &= dir_ret >= spec.min_dir_ret192_bps
    if spec.max_spread_bps is not None:
        mask &= frame["spread_bps"].to_numpy("float64") <= spec.max_spread_bps
    if spec.max_adverse_wick_atr is not None:
        lower = frame["lower_wick_atr"].to_numpy("float64")
        upper = frame["upper_wick_atr"].to_numpy("float64")
        adverse = np.where(filtered > 0, lower, upper)
        mask &= adverse <= spec.max_adverse_wick_atr
    if spec.min_close_pos is not None:
        long_pos = frame["long_close_pos"].to_numpy("float64")
        short_pos = frame["short_close_pos"].to_numpy("float64")
        close_pos = np.where(filtered > 0, long_pos, short_pos)
        mask &= close_pos >= spec.min_close_pos
    filtered[~mask] = 0
    return filtered


def simulate(
    frame: pd.DataFrame,
    signal: np.ndarray,
    frame_1m: pd.DataFrame | None,
    mode: Mode,
    *,
    config_id: str,
    arm_deadline_bars: int,
    max_hold_bars: int | None,
) -> list[Any]:
    ts = pd.to_datetime(frame["ts"], utc=True)
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    trades: list[Any] = []
    blocked_until = -1

    for sig_i in np.flatnonzero(signal):
        direction = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= len(frame) or entry_i <= blocked_until or direction == 0:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        entry_price = float(open_[entry_i] * (1.0 + direction * v33.ENTRY_SLIPPAGE_RATE))
        active_stop: float | None = None
        armed = False
        skip_open_gap_i: int | None = None
        reason = "time"
        exit_i = len(frame) - 1
        raw_exit = float(close[-1])

        for j in range(entry_i, len(frame)):
            bars_held = j - entry_i + 1
            if max_hold_bars is not None and bars_held > max_hold_bars:
                reason = "time_open"
                raw_exit = float(open_[j])
                exit_i = j
                break
            if armed and active_stop is not None:
                if j != skip_open_gap_i and not retry.armable(direction, active_stop, float(open_[j])):
                    reason = "gap_market_exit"
                    raw_exit = float(open_[j])
                    exit_i = j
                    break
                if retry.touched(direction, active_stop, float(high[j]), float(low[j])):
                    reason = "stop_market"
                    raw_exit = active_stop
                    exit_i = j
                    break
            if not armed and bars_held > arm_deadline_bars:
                reason = "stop_arm_deadline"
                raw_exit = float(close[j])
                exit_i = j
                break
            if bars_held < 7:
                continue

            desired_stop = trailed_stop_without_initial_floor(
                direction,
                entry_price,
                high[entry_i : j + 1],
                low[entry_i : j + 1],
                float(atr[j]),
                active_stop,
            )
            process_time = pd.Timestamp(ts.iloc[j]) + pd.Timedelta(minutes=5)
            next_time = process_time + pd.Timedelta(minutes=5)
            can_arm, _ = retry.interval_can_arm(
                mode,
                direction,
                desired_stop,
                float(close[j]),
                float(high[j + 1]) if j + 1 < len(frame) else None,
                float(low[j + 1]) if j + 1 < len(frame) else None,
                retry.one_minute_rows(frame_1m, process_time, next_time),
            )
            active_stop = desired_stop
            if can_arm:
                armed = True
                skip_open_gap_i = None if retry.armable(direction, desired_stop, float(close[j])) else j + 1

        exit_price = retry.exit_price_with_cost(raw_exit, direction)
        net, mae, mfe = retry.net_mae_mfe(direction, entry_price, exit_price, high[entry_i : exit_i + 1], low[entry_i : exit_i + 1])
        trades.append(
            v33.Trade(
                config=config_id,
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
    return {
        **config,
        "mode": mode,
        **v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end),
    }


def config_id(config: dict[str, Any]) -> str:
    max_hold = "none" if config["max_hold_bars"] is None else str(config["max_hold_bars"])
    return (
        f"pb{slug_float(float(config['pullback_buffer']))}"
        f"__{config['side_mode']}__{config['filter_name']}"
        f"__deadline{config['arm_deadline_bars']}__maxhold{max_hold}"
    )


def build_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    for pullback_buffer in PULLBACK_BUFFERS:
        for side_mode in ("both", "long", "short"):
            for filter_spec in FILTERS:
                for arm_deadline_bars in ARM_DEADLINES:
                    for max_hold_bars in MAX_HOLDS:
                        configs.append(
                            {
                                "config_id": "",
                                "pullback_buffer": pullback_buffer,
                                "side_mode": side_mode,
                                "filter_name": filter_spec.name,
                                "arm_deadline_bars": arm_deadline_bars,
                                "max_hold_bars": max_hold_bars,
                            }
                        )
                        configs[-1]["config_id"] = config_id(configs[-1])
    return configs


def render_markdown(prescreen: pd.DataFrame, full: pd.DataFrame, robust: pd.DataFrame, selected_count: int) -> str:
    def table(rows: pd.DataFrame) -> list[str]:
        output = ["| config | mode | trades | total | win | PF | payoff | max_dd |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for row in rows.to_dict(orient="records"):
            output.append(
                f"| `{row['config_id']}` | `{row['mode']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
                f"`{fmt_pct(float(row['win_rate']))}` | `{fmt_num(float(row['profit_factor']))}` | "
                f"`{fmt_num(float(row['payoff_ratio']))}` | `{fmt_pct(float(row['max_dd']))}` |"
            )
        return output

    lines = [
        "# HYPE-5M-PBTR-V3.3.1 rescue search 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告尝试在 V3.3.1 上“救活”旧 pullback-trailing 线：固定 no-initial-stop trailing overlay，扫描负/小 `pullback_buffer`、多空方向、信号 K 可得过滤器、`stop_arm_deadline` 和 `max_hold`。",
        "",
        "过滤器只使用信号 K 收盘前可得数据：`dir_ret192_bps`、EMA21/96 spread bps、方向性 adverse wick / ATR、方向性 close position。",
        "",
        f"Prescreen 配置数：`{len(prescreen)}`；进入四口径复核配置数：`{selected_count}`。",
        "",
        "## 5m conservative prescreen Top 20",
        "",
    ]
    lines.extend(table(prescreen.sort_values(["profit_factor", "total_return"], ascending=False).head(20)))
    lines.extend(["", "## 四口径复核 Top 30", ""])
    lines.extend(table(full.sort_values(["profit_factor", "total_return"], ascending=False).head(30)))
    lines.extend(["", "## Robust 聚合", ""])
    if robust.empty:
        lines.append("没有配置满足四口径交易数和 PF 同时可用的稳健条件。")
    else:
        lines.append("| config | min_trades | min_pf | min_total | max_dd_worst | modes |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for row in robust.sort_values(["min_pf", "min_total_return"], ascending=False).head(20).to_dict(orient="records"):
            lines.append(
                f"| `{row['config_id']}` | `{int(row['min_trades'])}` | `{fmt_num(float(row['min_pf']))}` | "
                f"`{fmt_pct(float(row['min_total_return']))}` | `{fmt_pct(float(row['worst_max_dd']))}` | `{int(row['modes'])}` |"
            )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "若 robust 表中没有 `min_trades >= 30` 且四口径 `min_pf > 1` 的配置，则本轮过滤/overlay 仍不能证明 V3.3.1 被救活。少量低样本正收益只能作为事件质量线索，不能直接进入 paper/live。",
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
        max_ts = min(pd.Timestamp(raw_5m["ts"].iloc[-1]), pd.Timestamp(frame_1m["ts"].iloc[-1]).floor("5min"))
        raw_5m = raw_5m.loc[raw_5m["ts"] <= max_ts].reset_index(drop=True)
        frame_1m = frame_1m.loc[
            (frame_1m["ts"] >= raw_5m["ts"].iloc[0]) & (frame_1m["ts"] <= max_ts + pd.Timedelta(minutes=5))
        ].reset_index(drop=True)

    frames: dict[float, tuple[pd.DataFrame, np.ndarray]] = {}
    for pullback_buffer in PULLBACK_BUFFERS:
        cfg = replace(v33.V33_CONFIG, pullback_buffer=pullback_buffer)
        frame = add_filter_features(v33.add_minimal_features(raw_5m, cfg))
        signal = v33.build_v33_signal(frame, cfg)
        frames[pullback_buffer] = (frame, signal)

    configs = build_configs()
    filter_by_name = {item.name: item for item in FILTERS}
    prescreen_rows: list[dict[str, Any]] = []
    for config in configs:
        frame, base_signal = frames[float(config["pullback_buffer"])]
        signal = apply_filters(base_signal, frame, config["side_mode"], filter_by_name[str(config["filter_name"])])
        if int(np.count_nonzero(signal)) < 5:
            continue
        trades = simulate(
            frame,
            signal,
            frame_1m,
            "5m_conservative",
            config_id=str(config["config_id"]),
            arm_deadline_bars=int(config["arm_deadline_bars"]),
            max_hold_bars=config["max_hold_bars"],
        )
        row = summarize(config, "5m_conservative", trades, frame)
        row["signal_count"] = int(np.count_nonzero(signal))
        prescreen_rows.append(row)

    prescreen = pd.DataFrame(prescreen_rows)
    selected = (
        prescreen.loc[prescreen["trades"].ge(20)]
        .sort_values(["profit_factor", "total_return"], ascending=False)
        .head(FULL_RECHECK_LIMIT)
    )
    selected_ids = set(selected["config_id"].tolist())
    full_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    modes: list[Mode] = ["5m_conservative", "5m_optimistic"]
    if frame_1m is not None:
        modes.extend(["1m_conservative", "1m_optimistic"])

    for config in configs:
        if config["config_id"] not in selected_ids:
            continue
        frame, base_signal = frames[float(config["pullback_buffer"])]
        signal = apply_filters(base_signal, frame, config["side_mode"], filter_by_name[str(config["filter_name"])])
        for mode in modes:
            trades = simulate(
                frame,
                signal,
                frame_1m,
                mode,
                config_id=str(config["config_id"]),
                arm_deadline_bars=int(config["arm_deadline_bars"]),
                max_hold_bars=config["max_hold_bars"],
            )
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
    if full.empty:
        robust = pd.DataFrame()
    else:
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
    MARKDOWN_PATH.write_text(render_markdown(prescreen, full, robust, len(selected_ids)), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V3.3.1",
                "audit": "rescue_search",
                "definition": {
                    "base": asdict(v33.V33_CONFIG),
                    "pullback_buffers": list(PULLBACK_BUFFERS),
                    "filters": [asdict(item) for item in FILTERS],
                    "arm_deadlines": list(ARM_DEADLINES),
                    "max_holds": list(MAX_HOLDS),
                    "full_recheck_limit": FULL_RECHECK_LIMIT,
                    "used_1m": frame_1m is not None,
                    "data_start": str(raw_5m["ts"].iloc[0]),
                    "data_end": str(raw_5m["ts"].iloc[-1]),
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "prescreen": str(PRESCREEN_PATH),
                    "full": str(FULL_PATH),
                    "robust": str(ROBUST_PATH),
                    "top_trades": str(TRADES_PATH),
                },
                "best_prescreen": prescreen.sort_values(["profit_factor", "total_return"], ascending=False)
                .head(20)
                .to_dict(orient="records"),
                "best_robust": robust.sort_values(["min_pf", "min_total_return"], ascending=False)
                .head(20)
                .to_dict(orient="records")
                if not robust.empty
                else [],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print("PRESCREEN TOP")
    print(prescreen.sort_values(["profit_factor", "total_return"], ascending=False).head(20)[["config_id", "trades", "total_return", "win_rate", "profit_factor", "max_dd"]].to_string(index=False))
    print("ROBUST TOP")
    if robust.empty:
        print("empty")
    else:
        print(robust.sort_values(["min_pf", "min_total_return"], ascending=False).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
