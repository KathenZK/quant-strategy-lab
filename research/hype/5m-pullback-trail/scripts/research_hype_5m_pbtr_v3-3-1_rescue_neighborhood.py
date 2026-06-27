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


rescue = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v3-3-1_rescue_search.py", "hype_pbtr_v331_rescue")
retry = rescue.retry
v33 = rescue.v33

RUN_DATE = "2026-06-27"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_rescue_neighborhood_{RUN_DATE}.json"
FULL_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_rescue_neighborhood_full_{RUN_DATE}.csv"
ROBUST_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_rescue_neighborhood_robust_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v3-3-1-rescue-neighborhood-{RUN_DATE}.md"

Mode = Literal["5m_conservative", "5m_optimistic", "1m_conservative", "1m_optimistic"]


@dataclass(frozen=True, slots=True)
class FilterSpec:
    name: str
    min_dir_ret192_bps: float | None
    max_spread_bps: float | None
    min_close_pos: float | None = None
    max_adverse_wick_atr: float | None = None


PULLBACK_BUFFERS = (-0.006, -0.0075, -0.009, -0.010, -0.011)
RET_THRESHOLDS = (0, 100, 150, 200, 250, 300, 400)
SPREAD_THRESHOLDS = (125, 150, 175, 200, 225, 250, 300)
CLOSE_POS_THRESHOLDS: tuple[float | None, ...] = (None, 0.55, 0.60, 0.70)
WICK_THRESHOLDS: tuple[float | None, ...] = (None, 0.25, 0.50)


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def filter_name(spec: FilterSpec) -> str:
    parts = [f"ret{int(spec.min_dir_ret192_bps or 0)}", f"spread{int(spec.max_spread_bps or 0)}"]
    if spec.min_close_pos is not None:
        parts.append(f"close{str(spec.min_close_pos).replace('.', 'p')}")
    if spec.max_adverse_wick_atr is not None:
        parts.append(f"wick{str(spec.max_adverse_wick_atr).replace('.', 'p')}")
    return "_".join(parts)


def config_id(pullback_buffer: float, spec: FilterSpec) -> str:
    return f"pb{rescue.slug_float(pullback_buffer)}__long__{filter_name(spec)}__deadline9__maxholdnone"


def build_specs() -> list[FilterSpec]:
    specs: list[FilterSpec] = []
    for ret in RET_THRESHOLDS:
        for spread in SPREAD_THRESHOLDS:
            for close_pos in CLOSE_POS_THRESHOLDS:
                for wick in WICK_THRESHOLDS:
                    specs.append(
                        FilterSpec(
                            name="",
                            min_dir_ret192_bps=float(ret) if ret else None,
                            max_spread_bps=float(spread),
                            min_close_pos=close_pos,
                            max_adverse_wick_atr=wick,
                        )
                    )
    return specs


def apply_filter(signal: np.ndarray, frame: pd.DataFrame, spec: FilterSpec) -> np.ndarray:
    filtered = signal.copy()
    mask = filtered > 0
    if spec.min_dir_ret192_bps is not None:
        mask &= frame["ret192_bps"].to_numpy("float64") >= spec.min_dir_ret192_bps
    if spec.max_spread_bps is not None:
        mask &= frame["spread_bps"].to_numpy("float64") <= spec.max_spread_bps
    if spec.min_close_pos is not None:
        mask &= frame["long_close_pos"].to_numpy("float64") >= spec.min_close_pos
    if spec.max_adverse_wick_atr is not None:
        mask &= frame["lower_wick_atr"].to_numpy("float64") <= spec.max_adverse_wick_atr
    filtered[~mask] = 0
    return filtered


def summarize(config: dict[str, Any], mode: Mode, trades: list[Any], frame: pd.DataFrame) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return {**config, "mode": mode, **v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end)}


def render_markdown(full: pd.DataFrame, robust: pd.DataFrame) -> str:
    lines = [
        "# HYPE-5M-PBTR-V3.3.1 rescue neighborhood 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告围绕上一轮 rescue search 的最佳区域做邻域搜索：`pullback_buffer≈-0.0075/-0.0100`、long-only、`dir_ret192_bps` 动量过滤、EMA21/96 spread 上限，并可选 close position / adverse wick 过滤。",
        "",
        "## Robust Top",
        "",
        "| config | min_trades | min_total | min_pf | worst_dd | avg_trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in robust.sort_values(["min_pf", "min_total_return"], ascending=False).head(30).to_dict(orient="records"):
        lines.append(
            f"| `{row['config_id']}` | `{int(row['min_trades'])}` | `{fmt_pct(float(row['min_total_return']))}` | "
            f"`{fmt_num(float(row['min_pf']))}` | `{fmt_pct(float(row['worst_max_dd']))}` | `{fmt_num(float(row['avg_trades']))}` |"
        )
    lines.extend(["", "## Full Top", ""])
    lines.append("| config | mode | trades | total | win | PF | max_dd |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for row in full.sort_values(["profit_factor", "total_return"], ascending=False).head(40).to_dict(orient="records"):
        lines.append(
            f"| `{row['config_id']}` | `{row['mode']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
            f"`{fmt_pct(float(row['win_rate']))}` | `{fmt_num(float(row['profit_factor']))}` | `{fmt_pct(float(row['max_dd']))}` |"
        )
    best = robust.sort_values(["min_pf", "min_total_return"], ascending=False).iloc[0]
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"邻域最佳四口径最差表现为 `{best['config_id']}`：min trades `{int(best['min_trades'])}`，min PF `{fmt_num(float(best['min_pf']))}`，min total `{fmt_pct(float(best['min_total_return']))}`，worst max drawdown `{fmt_pct(float(best['worst_max_dd']))}`。",
            "",
            "若该结果仍只有几十笔，需要继续做更长数据/跨样本或 walk-forward 复核，不能直接提升 live；但若四口径一致 PF>1，说明 V3.3.1 的可执行救活方向应转向“深回踩 long-only + 动量/位置过滤”，而不是继续保留高频双向原始信号。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- JSON：`{REPORT_PATH}`",
            f"- full CSV：`{FULL_PATH}`",
            f"- robust CSV：`{ROBUST_PATH}`",
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

    modes: list[Mode] = ["5m_conservative", "5m_optimistic"]
    if frame_1m is not None:
        modes.extend(["1m_conservative", "1m_optimistic"])

    frames: dict[float, tuple[pd.DataFrame, np.ndarray]] = {}
    for pullback_buffer in PULLBACK_BUFFERS:
        cfg = replace(v33.V33_CONFIG, pullback_buffer=pullback_buffer)
        frame = rescue.add_filter_features(v33.add_minimal_features(raw_5m, cfg))
        signal = v33.build_v33_signal(frame, cfg)
        frames[pullback_buffer] = (frame, signal)

    rows: list[dict[str, Any]] = []
    specs = build_specs()
    for pullback_buffer in PULLBACK_BUFFERS:
        frame, base_signal = frames[pullback_buffer]
        for spec in specs:
            signal = apply_filter(base_signal, frame, spec)
            signal_count = int(np.count_nonzero(signal))
            if signal_count < 10:
                continue
            config = {
                "config_id": config_id(pullback_buffer, spec),
                "pullback_buffer": pullback_buffer,
                "filter_name": filter_name(spec),
                "signal_count": signal_count,
                "min_dir_ret192_bps": spec.min_dir_ret192_bps,
                "max_spread_bps": spec.max_spread_bps,
                "min_close_pos": spec.min_close_pos,
                "max_adverse_wick_atr": spec.max_adverse_wick_atr,
            }
            for mode in modes:
                trades = rescue.simulate(
                    frame,
                    signal,
                    frame_1m,
                    mode,
                    config_id=str(config["config_id"]),
                    arm_deadline_bars=9,
                    max_hold_bars=None,
                )
                if len(trades) < 10:
                    continue
                rows.append(summarize(config, mode, trades, frame))

    full = pd.DataFrame(rows)
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
    robust = robust.loc[robust["modes"].eq(len(modes)) & robust["min_trades"].ge(10)].reset_index(drop=True)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    full.to_csv(FULL_PATH, index=False)
    robust.to_csv(ROBUST_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(full, robust), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V3.3.1",
                "audit": "rescue_neighborhood",
                "definition": {
                    "base": asdict(v33.V33_CONFIG),
                    "pullback_buffers": list(PULLBACK_BUFFERS),
                    "ret_thresholds": list(RET_THRESHOLDS),
                    "spread_thresholds": list(SPREAD_THRESHOLDS),
                    "close_pos_thresholds": list(CLOSE_POS_THRESHOLDS),
                    "wick_thresholds": list(WICK_THRESHOLDS),
                    "used_1m": frame_1m is not None,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "full": str(FULL_PATH),
                    "robust": str(ROBUST_PATH),
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
