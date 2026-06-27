from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
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


retry = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v33_retry_arm.py", "hype_pbtr_v33_retry_arm_pyramid")
v33 = retry.v33

RUN_DATE = "2026-06-27"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_armed_pyramiding_{RUN_DATE}.json"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_armed_pyramiding_summary_{RUN_DATE}.csv"
ROBUST_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_armed_pyramiding_robust_{RUN_DATE}.csv"
DIAG_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_armed_pyramiding_diag_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v3-3-1-armed-pyramiding-{RUN_DATE}.md"

Mode = Literal["5m_conservative", "5m_optimistic", "1m_conservative", "1m_optimistic"]


@dataclass(frozen=True, slots=True)
class PyramidConfig:
    add_mult: float
    min_stop_cushion_atr: float
    max_chase_atr: float
    require_locked_profit: bool = True

    @property
    def label(self) -> str:
        if self.add_mult <= 0:
            return "no_add_baseline"
        locked = "lock" if self.require_locked_profit else "nolock"
        return (
            f"add{self.add_mult:g}_cush{self.min_stop_cushion_atr:g}"
            f"_chase{self.max_chase_atr:g}_{locked}"
        )


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def build_configs() -> list[PyramidConfig]:
    configs = [PyramidConfig(add_mult=0.0, min_stop_cushion_atr=0.0, max_chase_atr=0.0)]
    for add_mult in (0.25, 0.5, 1.0):
        for min_stop_cushion_atr in (0.1, 0.3, 0.5, 0.8):
            for max_chase_atr in (0.5, 1.0, 1.5):
                for require_locked_profit in (True, False):
                    configs.append(
                        PyramidConfig(
                            add_mult=add_mult,
                            min_stop_cushion_atr=min_stop_cushion_atr,
                            max_chase_atr=max_chase_atr,
                            require_locked_profit=require_locked_profit,
                        )
                    )
    return configs


def raw_add_price(direction: int, close_price: float) -> float:
    return float(close_price * (1.0 + direction * v33.ENTRY_SLIPPAGE_RATE))


def leg_net(direction: int, entry_price: float, exit_price: float) -> float:
    gross = direction * (exit_price / entry_price - 1.0)
    fee_cost = v33.FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
    return float(gross - fee_cost)


def should_add(
    *,
    cfg: PyramidConfig,
    direction: int,
    original_entry: float,
    add_entry: float,
    active_stop: float,
    signal_atr: float,
) -> tuple[bool, str]:
    if cfg.add_mult <= 0:
        return False, "disabled"
    locked_net = direction * (active_stop / original_entry - 1.0) - 2.0 * v33.FEE_RATE_PER_FILL
    if cfg.require_locked_profit and locked_net <= 0:
        return False, "not_locked"
    stop_cushion_atr = direction * (add_entry - active_stop) / signal_atr
    if stop_cushion_atr < cfg.min_stop_cushion_atr:
        return False, "too_close_to_stop"
    chase_atr = direction * (add_entry - original_entry) / signal_atr
    if chase_atr > cfg.max_chase_atr:
        return False, "too_late_chase"
    if chase_atr < 0:
        return False, "not_favorable"
    return True, "added"


def simulate_pyramiding(
    frame: pd.DataFrame,
    signal: np.ndarray,
    frame_1m: pd.DataFrame | None,
    mode: Mode,
    cfg: PyramidConfig,
) -> tuple[list[Any], pd.DataFrame]:
    base_cfg = v33.V33_CONFIG
    ts = pd.to_datetime(frame["ts"], utc=True)
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    trades: list[Any] = []
    diag: list[dict[str, Any]] = []
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
        initial_stop = entry_price - direction * base_cfg.stop_atr * signal_atr
        active_stop = initial_stop
        armed = False
        arm_i: int | None = None
        skip_open_gap_i: int | None = None
        retry_count = 0
        reject_count = 0
        added = False
        add_i: int | None = None
        add_price: float | None = None
        add_skip_reason = "not_armed"
        reason = "time"
        exit_i = len(frame) - 1
        raw_exit = float(close[-1])

        for j in range(entry_i, len(frame)):
            bars_held = j - entry_i + 1
            if armed:
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
            if not armed and bars_held > 9:
                reason = "stop_arm_deadline"
                raw_exit = float(close[j])
                exit_i = j
                break
            if bars_held < 7:
                continue
            desired_stop = retry.trailed_stop(
                direction,
                entry_price,
                initial_stop,
                high[entry_i : j + 1],
                low[entry_i : j + 1],
                float(atr[j]),
                active_stop,
            )
            process_time = pd.Timestamp(ts.iloc[j]) + pd.Timedelta(minutes=5)
            next_time = process_time + pd.Timedelta(minutes=5)
            can_arm, retry_points = retry.interval_can_arm(
                mode,
                direction,
                desired_stop,
                float(close[j]),
                float(high[j + 1]) if j + 1 < len(frame) else None,
                float(low[j + 1]) if j + 1 < len(frame) else None,
                retry.one_minute_rows(frame_1m, process_time, next_time),
            )
            retry_count += retry_points
            active_stop = desired_stop
            if can_arm:
                armed = True
                arm_i = j
                close_armable = retry.armable(direction, desired_stop, float(close[j]))
                skip_open_gap_i = None if close_armable else j + 1
                if close_armable and not added:
                    candidate_add_price = raw_add_price(direction, float(close[j]))
                    add_ok, add_skip_reason = should_add(
                        cfg=cfg,
                        direction=direction,
                        original_entry=entry_price,
                        add_entry=candidate_add_price,
                        active_stop=desired_stop,
                        signal_atr=signal_atr,
                    )
                    if add_ok:
                        added = True
                        add_i = j
                        add_price = candidate_add_price
                elif cfg.add_mult > 0 and not added:
                    add_skip_reason = "arm_not_at_close"
            else:
                reject_count += 1

        exit_price = retry.exit_price_with_cost(raw_exit, direction)
        base_net, mae, mfe = retry.net_mae_mfe(
            direction,
            entry_price,
            exit_price,
            high[entry_i : exit_i + 1],
            low[entry_i : exit_i + 1],
        )
        add_net = 0.0
        if added and add_price is not None:
            add_net = leg_net(direction, add_price, exit_price)
        combo_net = base_net + cfg.add_mult * add_net
        trade = v33.Trade(
            config=f"{cfg.label}-{mode}",
            signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
            entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
            exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
            side=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            reason=reason,
            bars_held=int(exit_i - entry_i + 1),
            net_ret_1x=float(combo_net),
            mae_1x=mae,
            mfe_1x=mfe,
        )
        trades.append(trade)
        diag.append(
            {
                "config": cfg.label,
                "mode": mode,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": direction,
                "reason": reason,
                "bars_held": trade.bars_held,
                "armed": armed,
                "arm_ts": None if arm_i is None else pd.Timestamp(ts_ns[arm_i], unit="ns", tz="UTC"),
                "retry_count": retry_count,
                "reject_count": reject_count,
                "deadline_exit": reason == "stop_arm_deadline",
                "added": added,
                "add_ts": None if add_i is None else pd.Timestamp(ts_ns[add_i], unit="ns", tz="UTC"),
                "add_skip_reason": add_skip_reason,
                "add_mult": cfg.add_mult,
                "min_stop_cushion_atr": cfg.min_stop_cushion_atr,
                "max_chase_atr": cfg.max_chase_atr,
                "entry_price": entry_price,
                "add_price": add_price,
                "initial_stop": initial_stop,
                "final_active_stop": active_stop,
                "exit_price": exit_price,
                "base_net_ret_1x": base_net,
                "add_leg_net_ret_1x": add_net,
                "combo_net_ret_1x": combo_net,
                "mae_1x": mae,
                "mfe_1x": mfe,
            }
        )
        blocked_until = exit_i
    return trades, pd.DataFrame(diag)


def summarize(
    label: str,
    mode: Mode,
    trades: list[Any],
    frame: pd.DataFrame,
    diag: pd.DataFrame,
) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    metrics = v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end)
    return {
        "label": label,
        "mode": mode,
        **metrics,
        "armed_rate": float(diag["armed"].mean()) if len(diag) else np.nan,
        "added_rate": float(diag["added"].mean()) if len(diag) else np.nan,
        "added_of_armed_rate": float(diag.loc[diag["armed"], "added"].mean()) if bool(diag["armed"].any()) else np.nan,
        "deadline_exit_rate": float(diag["deadline_exit"].mean()) if len(diag) else np.nan,
        "avg_base_net": float(diag["base_net_ret_1x"].mean()) if len(diag) else np.nan,
        "avg_add_leg_net_when_added": float(diag.loc[diag["added"], "add_leg_net_ret_1x"].mean())
        if bool(diag["added"].any())
        else np.nan,
        "add_win_rate_when_added": float((diag.loc[diag["added"], "add_leg_net_ret_1x"] > 0).mean())
        if bool(diag["added"].any())
        else np.nan,
    }


def render_markdown(summary: pd.DataFrame, robust: pd.DataFrame, used_1m: bool) -> str:
    top = robust.sort_values(["min_pf", "min_total_return"], ascending=False).head(12)
    details = summary.sort_values(["profit_factor", "total_return"], ascending=False).head(80)
    best = top.iloc[0]
    lines = [
        "# HYPE-5M-PBTR-V3.3.1 armed-after pyramiding 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告测试用户提出的想法：V3.3.1 中 trailing stop 一旦成功 armed，原仓往往是盈利路径，那么在 armed 后给这笔订单增加杠杆/加仓是否能改善整体收益。",
        "",
        "## 口径",
        "",
        "- 基础状态机沿用 V3.3.1 retry-arm：第 7 根开始尝试挂 stop，第 10 根兜底市价平。",
        "- 加仓只在 stop-arm 于 5m 收盘处理价已经可挂时触发；如果只是 optimistic 口径假设下一段可能回到可挂区，不额外假设同步加仓。",
        "- 加仓腿与原仓共用当时 active trailing stop；组合收益按 `base_net + add_mult * add_leg_net` 计入，代表额外杠杆暴露。",
        "- 网格分两类：`lock` 要求 stop 已锁住原仓扣成本后利润；`nolock` 只要求当前 armed 后浮盈、距离 stop 足够远且没有追得过远。",
        f"- 本次使用 1m 数据：`{used_1m}`。",
        "",
        "## Robust Top",
        "",
        "| config | modes | min trades | min total | min PF | min added | worst DD |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in top.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['modes'])}` | `{int(row['min_trades'])}` | "
            f"`{fmt_pct(float(row['min_total_return']))}` | `{fmt_num(float(row['min_pf']))}` | "
            f"`{fmt_pct(float(row['min_added_rate']))}` | `{fmt_pct(float(row['worst_dd']))}` |"
        )
    lines.extend(["", "## 四口径明细 Top", ""])
    lines.append("| config | mode | trades | total | PF | win | payoff | added | add win | add avg | DD |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in details.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['mode']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
            f"`{fmt_num(float(row['profit_factor']))}` | `{fmt_pct(float(row['win_rate']))}` | `{fmt_num(float(row['payoff_ratio']))}` | "
            f"`{fmt_pct(float(row['added_rate']))}` | `{fmt_pct(float(row['add_win_rate_when_added']))}` | "
            f"`{fmt_pct(float(row['avg_add_leg_net_when_added']))}` | `{fmt_pct(float(row['max_dd']))}` |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"四口径最强 robust 配置为 `{best['label']}`：min PF `{fmt_num(float(best['min_pf']))}`，min total `{fmt_pct(float(best['min_total_return']))}`，worst drawdown `{fmt_pct(float(best['worst_dd']))}`。",
            "",
            "如果最强配置仍低于 PF `1`，说明 armed 后加仓没有救回全量 V3.3.1；它最多说明 armed/trailing 子路径有一定趋势延续，但新增仓位是在更差价格进场，回打到同一个 trailing stop 时会显著稀释原仓利润。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- JSON：`{REPORT_PATH}`",
            f"- summary CSV：`{SUMMARY_PATH}`",
            f"- robust CSV：`{ROBUST_PATH}`",
            f"- diag CSV：`{DIAG_PATH}`",
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

    frame = v33.add_minimal_features(raw_5m, v33.V33_CONFIG)
    signal = v33.build_v33_signal(frame, v33.V33_CONFIG)
    modes: list[Mode] = ["5m_conservative", "5m_optimistic"]
    if frame_1m is not None:
        modes.extend(["1m_conservative", "1m_optimistic"])

    rows: list[dict[str, Any]] = []
    diag_frames: list[pd.DataFrame] = []
    for cfg in build_configs():
        for mode in modes:
            trades, diag = simulate_pyramiding(frame, signal, frame_1m, mode, cfg)
            rows.append(summarize(cfg.label, mode, trades, frame, diag))
            diag_frames.append(diag)

    summary = pd.DataFrame(rows)
    robust = (
        summary.groupby("label")
        .agg(
            modes=("mode", "nunique"),
            min_trades=("trades", "min"),
            min_total_return=("total_return", "min"),
            min_pf=("profit_factor", "min"),
            min_added_rate=("added_rate", "min"),
            worst_dd=("max_dd", "min"),
            avg_add_leg_net=("avg_add_leg_net_when_added", "mean"),
        )
        .reset_index()
    )
    diag = pd.concat(diag_frames, ignore_index=True)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    robust.to_csv(ROBUST_PATH, index=False)
    diag.to_csv(DIAG_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, robust, frame_1m is not None), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V3.3.1",
                "audit": "armed_after_pyramiding",
                "base": asdict(v33.V33_CONFIG),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "robust": str(ROBUST_PATH),
                    "diag": str(DIAG_PATH),
                },
                "top_robust": robust.sort_values(["min_pf", "min_total_return"], ascending=False)
                .head(20)
                .to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(robust.sort_values(["min_pf", "min_total_return"], ascending=False).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
