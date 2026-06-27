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

REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_filter_directions_{RUN_DATE}.json"
FULL_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_filter_directions_full_{RUN_DATE}.csv"
ROBUST_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_filter_directions_robust_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_filter_directions_top_trades_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v3-3-1-filter-directions-{RUN_DATE}.md"

Mode = Literal["5m_conservative", "5m_optimistic", "1m_conservative", "1m_optimistic"]


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def add_filter_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    open_ = result["open"]
    high = result["high"]
    low = result["low"]
    close = result["close"]
    atr = result["atr14"].replace(0, np.nan)
    ema21 = result["ema21"]
    ema96 = result["ema96"]
    candle_range = (high - low).replace(0, np.nan)

    result["body_atr"] = (close - open_).abs() / atr
    result["ema21_slope3_bps"] = (ema21 / ema21.shift(3) - 1.0) * 10000.0
    result["ema21_slope6_bps"] = (ema21 / ema21.shift(6) - 1.0) * 10000.0
    result["ema21_slope12_bps"] = (ema21 / ema21.shift(12) - 1.0) * 10000.0
    result["long_pullback_depth_atr"] = np.maximum(0.0, (ema21 - low) / atr)
    result["short_pullback_depth_atr"] = np.maximum(0.0, (high - ema21) / atr)
    result["atr14_over_atr96"] = result["atr14"] / result["atr14"].rolling(96, min_periods=96).mean()
    result["long_close_pos"] = (close - low) / candle_range
    result["short_close_pos"] = (high - close) / candle_range
    result["ema_spread_bps"] = (ema21 - ema96) / close * 10000.0
    result["dir_ret192_bps"] = (close / close.shift(192) - 1.0) * 10000.0

    htf = result.set_index("ts")[["open", "high", "low", "close"]].resample("1h", label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    htf = htf.dropna()
    htf["ema21_1h"] = htf["close"].ewm(span=21, adjust=False, min_periods=21).mean()
    htf["ema96_1h"] = htf["close"].ewm(span=96, adjust=False, min_periods=96).mean()
    htf["htf_ema_spread_bps"] = (htf["ema21_1h"] - htf["ema96_1h"]) / htf["close"] * 10000.0
    result = pd.merge_asof(
        result.sort_values("ts"),
        htf[["htf_ema_spread_bps"]].reset_index().sort_values("ts"),
        on="ts",
        direction="backward",
    )
    return result


def base_mask(signal: np.ndarray) -> np.ndarray:
    return signal != 0


def direction_values(signal: np.ndarray, long_values: np.ndarray, short_values: np.ndarray) -> np.ndarray:
    return np.where(signal > 0, long_values, short_values)


def apply_named_filter(signal: np.ndarray, frame: pd.DataFrame, name: str) -> np.ndarray:
    mask = base_mask(signal)
    direction = signal.astype("float64")
    if name == "base":
        pass
    elif name == "body_atr_ge_0p10":
        mask &= frame["body_atr"].to_numpy("float64") >= 0.10
    elif name == "body_atr_ge_0p20":
        mask &= frame["body_atr"].to_numpy("float64") >= 0.20
    elif name == "body_atr_ge_0p30":
        mask &= frame["body_atr"].to_numpy("float64") >= 0.30
    elif name == "slope3_same_ge_0":
        mask &= direction * frame["ema21_slope3_bps"].to_numpy("float64") >= 0.0
    elif name == "slope6_same_ge_0":
        mask &= direction * frame["ema21_slope6_bps"].to_numpy("float64") >= 0.0
    elif name == "slope6_same_ge_5":
        mask &= direction * frame["ema21_slope6_bps"].to_numpy("float64") >= 5.0
    elif name == "slope12_same_ge_0":
        mask &= direction * frame["ema21_slope12_bps"].to_numpy("float64") >= 0.0
    elif name == "depth_atr_le_0p25":
        depth = direction_values(
            signal,
            frame["long_pullback_depth_atr"].to_numpy("float64"),
            frame["short_pullback_depth_atr"].to_numpy("float64"),
        )
        mask &= depth <= 0.25
    elif name == "depth_atr_le_0p50":
        depth = direction_values(
            signal,
            frame["long_pullback_depth_atr"].to_numpy("float64"),
            frame["short_pullback_depth_atr"].to_numpy("float64"),
        )
        mask &= depth <= 0.50
    elif name == "depth_atr_le_0p75":
        depth = direction_values(
            signal,
            frame["long_pullback_depth_atr"].to_numpy("float64"),
            frame["short_pullback_depth_atr"].to_numpy("float64"),
        )
        mask &= depth <= 0.75
    elif name == "atr_stable_le_1p0":
        mask &= frame["atr14_over_atr96"].to_numpy("float64") <= 1.0
    elif name == "atr_stable_le_1p25":
        mask &= frame["atr14_over_atr96"].to_numpy("float64") <= 1.25
    elif name == "atr_stable_le_1p50":
        mask &= frame["atr14_over_atr96"].to_numpy("float64") <= 1.50
    elif name == "htf_1h_same":
        mask &= direction * frame["htf_ema_spread_bps"].to_numpy("float64") > 0.0
    elif name == "htf_1h_same_25bps":
        mask &= direction * frame["htf_ema_spread_bps"].to_numpy("float64") >= 25.0
    elif name == "close_pos_ge_0p60":
        close_pos = direction_values(
            signal,
            frame["long_close_pos"].to_numpy("float64"),
            frame["short_close_pos"].to_numpy("float64"),
        )
        mask &= close_pos >= 0.60
    elif name == "ret192_same_ge_250":
        mask &= direction * frame["dir_ret192_bps"].to_numpy("float64") >= 250.0
    elif name == "spread_abs_ge_50":
        mask &= np.abs(frame["ema_spread_bps"].to_numpy("float64")) >= 50.0
    elif name == "combo_body_slope_depth":
        close_pos = direction_values(
            signal,
            frame["long_close_pos"].to_numpy("float64"),
            frame["short_close_pos"].to_numpy("float64"),
        )
        depth = direction_values(
            signal,
            frame["long_pullback_depth_atr"].to_numpy("float64"),
            frame["short_pullback_depth_atr"].to_numpy("float64"),
        )
        mask &= frame["body_atr"].to_numpy("float64") >= 0.20
        mask &= direction * frame["ema21_slope6_bps"].to_numpy("float64") >= 0.0
        mask &= depth <= 0.50
        mask &= close_pos >= 0.60
    elif name == "combo_slope_atr_htf":
        mask &= direction * frame["ema21_slope6_bps"].to_numpy("float64") >= 0.0
        mask &= frame["atr14_over_atr96"].to_numpy("float64") <= 1.25
        mask &= direction * frame["htf_ema_spread_bps"].to_numpy("float64") > 0.0
    elif name == "combo_ret_spread":
        mask &= direction * frame["dir_ret192_bps"].to_numpy("float64") >= 250.0
        mask &= np.abs(frame["ema_spread_bps"].to_numpy("float64")) >= 50.0
    else:
        raise ValueError(f"unknown filter: {name}")

    filtered = signal.copy()
    filtered[~mask] = 0
    return filtered


FILTER_NAMES = (
    "base",
    "body_atr_ge_0p10",
    "body_atr_ge_0p20",
    "body_atr_ge_0p30",
    "slope3_same_ge_0",
    "slope6_same_ge_0",
    "slope6_same_ge_5",
    "slope12_same_ge_0",
    "depth_atr_le_0p25",
    "depth_atr_le_0p50",
    "depth_atr_le_0p75",
    "atr_stable_le_1p0",
    "atr_stable_le_1p25",
    "atr_stable_le_1p50",
    "htf_1h_same",
    "htf_1h_same_25bps",
    "close_pos_ge_0p60",
    "ret192_same_ge_250",
    "spread_abs_ge_50",
    "combo_body_slope_depth",
    "combo_slope_atr_htf",
    "combo_ret_spread",
)


def summarize(filter_name: str, mode: Mode, trades: list[Any], frame: pd.DataFrame, signal_count: int) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return {
        "filter": filter_name,
        "mode": mode,
        "signal_count": signal_count,
        **v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end),
    }


def render_markdown(full: pd.DataFrame, robust: pd.DataFrame, used_1m: bool) -> str:
    lines = [
        "# HYPE-5M-PBTR-V3.3.1 filter directions 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告把昨晚实盘复盘提出的五类过滤方向放到 V3.3.1 上回测：反抽实体强度、EMA21 斜率同向、回踩深度上限、ATR 稳定、1h EMA 大周期确认，并附加少量组合过滤。",
        "",
        "口径：使用本地 1m/5m 重叠区间，四口径复核 `5m_conservative`、`5m_optimistic`、`1m_conservative`、`1m_optimistic`。优化目标看交易数、收益、胜率、PF、payoff、MAE/回撤，不看昨晚小样本的 trailing/deadline 比例。",
        "",
        f"本次使用 1m 数据：`{used_1m}`。",
        "",
        "## Robust 聚合",
        "",
        "| filter | min_trades | min_total | min_pf | min_win | worst_dd | worst_mae | modes |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in robust.sort_values(["min_pf", "min_total_return"], ascending=False).to_dict(orient="records"):
        lines.append(
            f"| `{row['filter']}` | `{int(row['min_trades'])}` | `{fmt_pct(float(row['min_total_return']))}` | "
            f"`{fmt_num(float(row['min_pf']))}` | `{fmt_pct(float(row['min_win_rate']))}` | "
            f"`{fmt_pct(float(row['worst_max_dd']))}` | `{fmt_pct(float(row['worst_trade_mae']))}` | `{int(row['modes'])}` |"
        )
    lines.extend(["", "## 四口径明细 Top", ""])
    lines.append("| filter | mode | trades | total | win | PF | payoff | max_dd | worst_trade |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in full.sort_values(["profit_factor", "total_return"], ascending=False).head(60).to_dict(orient="records"):
        lines.append(
            f"| `{row['filter']}` | `{row['mode']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
            f"`{fmt_pct(float(row['win_rate']))}` | `{fmt_num(float(row['profit_factor']))}` | "
            f"`{fmt_num(float(row['payoff_ratio']))}` | `{fmt_pct(float(row['max_dd']))}` | `{fmt_pct(float(row['worst_trade']))}` |"
        )
    best = robust.sort_values(["min_pf", "min_total_return"], ascending=False).iloc[0]
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"四口径最强过滤为 `{best['filter']}`：min trades `{int(best['min_trades'])}`，min total `{fmt_pct(float(best['min_total_return']))}`，min PF `{fmt_num(float(best['min_pf']))}`，worst max drawdown `{fmt_pct(float(best['worst_max_dd']))}`。",
            "",
            "若全部过滤的 min PF 仍低于 `1`，说明这些单独过滤不能救回全量 V3.3.1；若某些过滤改善 MAE/回撤但收益仍亏，说明它们可作为 rescue 子集建模特征，而不是直接上线规则。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- JSON：`{REPORT_PATH}`",
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

    frame = add_filter_features(v33.add_minimal_features(raw_5m, v33.V33_CONFIG))
    base_signal = v33.build_v33_signal(frame, v33.V33_CONFIG)
    modes: list[Mode] = ["5m_conservative", "5m_optimistic"]
    if frame_1m is not None:
        modes.extend(["1m_conservative", "1m_optimistic"])

    rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    for filter_name in FILTER_NAMES:
        signal = apply_named_filter(base_signal, frame, filter_name)
        signal_count = int(np.count_nonzero(signal))
        if signal_count == 0:
            continue
        for mode in modes:
            trades, _diag = retry.simulate_retry_arm(frame, signal, frame_1m, mode)
            rows.append(summarize(filter_name, mode, trades, frame, signal_count))
            if mode == "5m_conservative":
                for i, trade in enumerate(trades[:100], start=1):
                    trade_rows.append(
                        {
                            "filter": filter_name,
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

    full = pd.DataFrame(rows)
    robust = (
        full.groupby("filter")
        .agg(
            modes=("mode", "nunique"),
            min_trades=("trades", "min"),
            min_total_return=("total_return", "min"),
            min_pf=("profit_factor", "min"),
            min_win_rate=("win_rate", "min"),
            worst_max_dd=("max_dd", "min"),
            worst_trade_mae=("worst_trade", "min"),
            avg_trades=("trades", "mean"),
        )
        .reset_index()
    )
    robust = robust.loc[robust["modes"].eq(len(modes))].reset_index(drop=True)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    full.to_csv(FULL_PATH, index=False)
    robust.to_csv(ROBUST_PATH, index=False)
    pd.DataFrame(trade_rows).to_csv(TRADES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(full, robust, frame_1m is not None), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V3.3.1",
                "audit": "filter_directions",
                "definition": {
                    "base": asdict(v33.V33_CONFIG),
                    "filters": list(FILTER_NAMES),
                    "used_1m": frame_1m is not None,
                    "data_start": str(frame["ts"].iloc[0]),
                    "data_end": str(frame["ts"].iloc[-1]),
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "full": str(FULL_PATH),
                    "robust": str(ROBUST_PATH),
                    "top_trades": str(TRADES_PATH),
                },
                "best_robust": robust.sort_values(["min_pf", "min_total_return"], ascending=False).to_dict(
                    orient="records"
                ),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(robust.sort_values(["min_pf", "min_total_return"], ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
