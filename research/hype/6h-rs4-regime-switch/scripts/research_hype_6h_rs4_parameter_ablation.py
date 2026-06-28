from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SOURCE_PATH = Path(__file__).with_name("research_hype_6h_rs4_backtest.py")

FAMILY_ROOT = Path("research/hype/6h-rs4-regime-switch")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAG_ROOT = FAMILY_ROOT / "diagnostics"

SUMMARY_JSON = ARTIFACT_ROOT / "hype_6h_rs4_parameter_ablation_summary_2026-06-28.json"
ABLATION_CSV = ARTIFACT_ROOT / "hype_6h_rs4_parameter_ablation_2026-06-28.csv"
SLICE_CSV = ARTIFACT_ROOT / "hype_6h_rs4_parameter_slices_2026-06-28.csv"
ROLLING_CSV = ARTIFACT_ROOT / "hype_6h_rs4_parameter_rolling21d_2026-06-28.csv"
REPORT_MD = DIAG_ROOT / "hype-6h-rs4-parameter-ablation-stability-2026-06-28.md"


def load_base_module() -> Any:
    spec = importlib.util.spec_from_file_location("hype_6h_rs4_backtest", SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {SOURCE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base_module()


@dataclass(frozen=True, slots=True)
class Rs4Spec:
    name: str = "baseline"
    group: str = "baseline"
    changed_parameter: str = "baseline"
    changed_value: str = "baseline"
    range_window: int = 12
    range_threshold: float = 0.12
    v10_use_range_gate: bool = True
    macd_fast: int = 8
    macd_slow: int = 21
    macd_signal: int = 5
    long_persist: int = 2
    atr_window: int = 28
    use_mfeu: bool = True
    mfe_trigger_atr: float = 2.0
    mfe_giveback_atr: float = 1.5
    first_flat_exemption: bool = True
    breakeven_guard: bool = True
    melt_use_range_gate: bool = True
    er_window: int = 20
    er_threshold: float = 0.35
    use_er_gate: bool = True
    donchian_entry: int = 20
    donchian_exit: int = 10
    use_donchian: bool = True
    melt_side_mode: str = "long"
    weight: float = 1.0
    cost_multiplier: float = 1.0
    use_funding: bool = True


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def num(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def variant(base_spec: Rs4Spec, *, group: str, parameter: str, value: Any, **changes: Any) -> Rs4Spec:
    safe_value = str(value).replace(" ", "_").replace("/", "_")
    return replace(
        base_spec,
        name=f"{group}__{parameter}={safe_value}",
        group=group,
        changed_parameter=parameter,
        changed_value=str(value),
        **changes,
    )


def ablation_specs() -> list[Rs4Spec]:
    baseline = Rs4Spec()
    specs = [baseline]
    specs.extend(
        [
            variant(baseline, group="combo_weight", parameter="w", value=0.0, weight=0.0),
            variant(baseline, group="combo_weight", parameter="w", value=0.5, weight=0.5),
            variant(baseline, group="combo_weight", parameter="w", value=1.5, weight=1.5),
            variant(baseline, group="combo_weight", parameter="w", value=2.0, weight=2.0),
        ]
    )
    specs.extend(
        [
            variant(baseline, group="v10_range_gate", parameter="range_gate", value="off", v10_use_range_gate=False),
            *[
                variant(baseline, group="v10_range_threshold", parameter="range_threshold", value=value, range_threshold=value)
                for value in (0.10, 0.11, 0.13, 0.14, 0.16)
            ],
            *[
                variant(baseline, group="range_window", parameter="range_window", value=value, range_window=value)
                for value in (8, 10, 14, 16)
            ],
        ]
    )
    specs.extend(
        [
            *[variant(baseline, group="macd_fast", parameter="macd_fast", value=value, macd_fast=value) for value in (6, 10, 12)],
            *[variant(baseline, group="macd_slow", parameter="macd_slow", value=value, macd_slow=value) for value in (18, 24, 30)],
            *[variant(baseline, group="macd_signal", parameter="macd_signal", value=value, macd_signal=value) for value in (3, 7, 9)],
            *[variant(baseline, group="long_persist", parameter="long_persist", value=value, long_persist=value) for value in (1, 3, 4)],
        ]
    )
    specs.extend(
        [
            variant(baseline, group="mfeu", parameter="use_mfeu", value="off", use_mfeu=False),
            variant(
                baseline,
                group="mfeu",
                parameter="first_flat_exemption",
                value="off",
                first_flat_exemption=False,
            ),
            variant(baseline, group="mfeu", parameter="breakeven_guard", value="off", breakeven_guard=False),
            *[
                variant(baseline, group="mfe_trigger", parameter="mfe_trigger_atr", value=value, mfe_trigger_atr=value)
                for value in (1.5, 2.5, 3.0)
            ],
            *[
                variant(baseline, group="mfe_giveback", parameter="mfe_giveback_atr", value=value, mfe_giveback_atr=value)
                for value in (1.0, 2.0, 2.5)
            ],
            *[variant(baseline, group="atr_window", parameter="atr_window", value=value, atr_window=value) for value in (14, 21, 35, 42)],
        ]
    )
    specs.extend(
        [
            variant(baseline, group="melt_range_gate", parameter="melt_range_gate", value="off", melt_use_range_gate=False),
            *[
                variant(baseline, group="melt_range_threshold", parameter="range_threshold", value=value, range_threshold=value)
                for value in (0.10, 0.11, 0.13, 0.14, 0.16)
            ],
            variant(baseline, group="er_gate", parameter="use_er_gate", value="off", use_er_gate=False),
            *[variant(baseline, group="er_window", parameter="er_window", value=value, er_window=value) for value in (10, 14, 30)],
            *[
                variant(baseline, group="er_threshold", parameter="er_threshold", value=value, er_threshold=value)
                for value in (0.25, 0.30, 0.40, 0.45, 0.50)
            ],
        ]
    )
    specs.extend(
        [
            variant(baseline, group="melt_side", parameter="melt_side_mode", value="both", melt_side_mode="both"),
            variant(baseline, group="melt_side", parameter="melt_side_mode", value="short", melt_side_mode="short"),
            variant(baseline, group="donchian", parameter="use_donchian", value="off", use_donchian=False),
            *[
                variant(baseline, group="donchian_entry", parameter="donchian_entry", value=value, donchian_entry=value)
                for value in (10, 15, 25, 30)
            ],
            *[
                variant(baseline, group="donchian_exit", parameter="donchian_exit", value=value, donchian_exit=value)
                for value in (5, 15, 20)
            ],
        ]
    )
    specs.extend(
        [
            variant(baseline, group="costs", parameter="cost_multiplier", value=0.0, cost_multiplier=0.0),
            variant(baseline, group="costs", parameter="cost_multiplier", value=2.0, cost_multiplier=2.0),
            variant(baseline, group="funding", parameter="use_funding", value="off", use_funding=False),
        ]
    )
    return specs


def attach_features_for_spec(bars: pd.DataFrame, funding: pd.DataFrame, spec: Rs4Spec) -> pd.DataFrame:
    frame = bars.copy()
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]

    frame["range"] = high.rolling(spec.range_window).max() / low.rolling(spec.range_window).min() - 1.0
    ema_fast = close.ewm(span=spec.macd_fast, adjust=False, min_periods=spec.macd_fast).mean()
    ema_slow = close.ewm(span=spec.macd_slow, adjust=False, min_periods=spec.macd_slow).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=spec.macd_signal, adjust=False, min_periods=spec.macd_signal).mean()
    frame["macd_hist"] = macd - signal
    positive = frame["macd_hist"] > 0
    frame["macd_long_ok"] = positive.rolling(spec.long_persist).sum() >= spec.long_persist

    prev_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr_pct"] = true_range.rolling(spec.atr_window).mean() / close

    net_move = (close - close.shift(spec.er_window)).abs()
    path = close.diff().abs().rolling(spec.er_window).sum()
    frame["er"] = net_move / path.replace(0.0, np.nan)
    frame["hi_entry_prev"] = high.shift(1).rolling(spec.donchian_entry).max()
    frame["lo_entry_prev"] = low.shift(1).rolling(spec.donchian_entry).min()
    frame["hi_exit_prev"] = high.shift(1).rolling(spec.donchian_exit).max()
    frame["lo_exit_prev"] = low.shift(1).rolling(spec.donchian_exit).min()
    frame["open_ret_next"] = frame["open"].shift(-1) / frame["open"] - 1.0

    if funding.empty:
        frame["funding_sum"] = 0.0
    else:
        funding = funding.copy()
        funding["bar_ts"] = pd.to_datetime(funding["ts"], utc=True).dt.floor("6h")
        funding_sum = funding.groupby("bar_ts")["funding_rate"].sum()
        frame["funding_sum"] = pd.to_datetime(frame["ts"], utc=True).map(funding_sum).fillna(0.0).astype(float)
    return frame


def v10_signal(frame: pd.DataFrame, i: int, spec: Rs4Spec) -> int:
    hist = float(frame.at[i, "macd_hist"])
    if not np.isfinite(hist):
        return 0
    gate = bool(frame.at[i, "range"] <= spec.range_threshold) if spec.v10_use_range_gate else True
    if not gate:
        return 0
    if hist < 0:
        return -1
    if bool(frame.at[i, "macd_long_ok"]):
        return 1
    return 0


def simulate_v10(frame: pd.DataFrame, spec: Rs4Spec) -> np.ndarray:
    n = len(frame)
    pos = np.zeros(n, dtype="int8")
    current = 0
    entry_price = np.nan
    entry_atr = np.nan
    peak_favorable = 0.0
    close_favorable = 0.0
    qualified = False
    first_flat_ignored = False

    for i in range(n - 1):
        pos[i] = current
        if current != 0 and np.isfinite(entry_price):
            if current > 0:
                favorable = float(frame.at[i, "high"] / entry_price - 1.0)
                close_favorable = float(frame.at[i, "close"] / entry_price - 1.0)
            else:
                favorable = float(entry_price / frame.at[i, "low"] - 1.0)
                close_favorable = float(entry_price / frame.at[i, "close"] - 1.0)
            peak_favorable = max(peak_favorable, favorable)
            if spec.use_mfeu and np.isfinite(entry_atr) and peak_favorable >= spec.mfe_trigger_atr * entry_atr:
                qualified = True

        base_signal = v10_signal(frame, i, spec)
        target = base_signal
        if current != 0 and base_signal == 0 and spec.use_mfeu and qualified:
            if spec.first_flat_exemption and not first_flat_ignored:
                target = current
                first_flat_ignored = True
            else:
                giveback = peak_favorable - close_favorable
                breakeven_ok = (close_favorable > 0.0) if spec.breakeven_guard else True
                if breakeven_ok and giveback < spec.mfe_giveback_atr * entry_atr:
                    target = current
                else:
                    target = 0

        if target != current:
            if target != 0:
                entry_price = float(frame.at[i + 1, "open"])
                entry_atr = float(frame.at[i, "atr_pct"])
                peak_favorable = 0.0
                close_favorable = 0.0
                qualified = False
                first_flat_ignored = False
            else:
                entry_price = np.nan
                entry_atr = np.nan
                peak_favorable = 0.0
                close_favorable = 0.0
                qualified = False
                first_flat_ignored = False
        current = target

    pos[-1] = current
    return pos


def melt_target(frame: pd.DataFrame, i: int, current: int, spec: Rs4Spec) -> int:
    range_value = float(frame.at[i, "range"])
    er_value = float(frame.at[i, "er"])
    close = float(frame.at[i, "close"])
    range_gate = (np.isfinite(range_value) and range_value > spec.range_threshold) if spec.melt_use_range_gate else True
    er_gate = (np.isfinite(er_value) and er_value >= spec.er_threshold) if spec.use_er_gate else True
    gate = range_gate and er_gate

    if not spec.use_donchian:
        if not gate:
            return 0
        if spec.melt_side_mode == "short":
            return -1
        return 1

    if current > 0:
        if (not gate) or close < float(frame.at[i, "lo_exit_prev"]):
            return 0
        return 1
    if current < 0:
        if (not gate) or close > float(frame.at[i, "hi_exit_prev"]):
            return 0
        return -1

    if gate and spec.melt_side_mode in {"long", "both"} and close > float(frame.at[i, "hi_entry_prev"]):
        return 1
    if gate and spec.melt_side_mode in {"short", "both"} and close < float(frame.at[i, "lo_entry_prev"]):
        return -1
    return 0


def simulate_melt(frame: pd.DataFrame, spec: Rs4Spec) -> np.ndarray:
    n = len(frame)
    pos = np.zeros(n, dtype="int8")
    current = 0
    for i in range(n - 1):
        pos[i] = current
        current = melt_target(frame, i, current, spec)
    pos[-1] = current
    return pos


def leg_returns(name: str, frame: pd.DataFrame, positions: np.ndarray, spec: Rs4Spec) -> Any:
    pos = positions.astype(float)
    prev = np.roll(pos, 1)
    prev[0] = 0.0
    turnover = np.abs(pos - prev)
    open_ret_next = frame["open_ret_next"].fillna(0.0).to_numpy("float64")
    funding_sum = frame["funding_sum"].fillna(0.0).to_numpy("float64") if spec.use_funding else np.zeros(len(frame))
    one_way_cost = base.ONE_WAY_COST * spec.cost_multiplier
    returns = pos * open_ret_next - turnover * one_way_cost - pos * funding_sum
    returns[-1] = 0.0
    trades = base.extract_trades(name, frame, positions, returns)
    return base.StrategyReturns(name=name, frame=frame, positions=positions, returns=returns, trades=trades)


def run_spec(frame: pd.DataFrame, spec: Rs4Spec) -> Any:
    v10 = leg_returns("v10", frame, simulate_v10(frame, spec), spec)
    melt = leg_returns("melt", frame, simulate_melt(frame, spec), spec)
    combined_returns = v10.returns + spec.weight * melt.returns
    combined_positions = v10.positions + spec.weight * melt.positions
    return base.StrategyReturns(
        name=spec.name,
        frame=frame,
        positions=combined_positions,
        returns=combined_returns,
        trades=[*v10.trades, *melt.trades],
    )


def fixed_slices(frame: pd.DataFrame) -> dict[str, tuple[pd.Timestamp | None, pd.Timestamp | None]]:
    return {
        "full": (None, None),
        "early_2025_05_30_to_2025_09_01": (pd.Timestamp("2025-05-30T00:00:00Z"), pd.Timestamp("2025-09-01T00:00:00Z")),
        "mid_2025_09_01_to_2025_12_01": (pd.Timestamp("2025-09-01T00:00:00Z"), pd.Timestamp("2025-12-01T00:00:00Z")),
        "late_2025_12_01_to_2026_03_01": (pd.Timestamp("2025-12-01T00:00:00Z"), pd.Timestamp("2026-03-01T00:00:00Z")),
        "spring_2026_03_01_to_2026_06_01": (pd.Timestamp("2026-03-01T00:00:00Z"), pd.Timestamp("2026-06-01T00:00:00Z")),
        "post_funding_gap_2026_06_01_latest": (pd.Timestamp("2026-06-01T00:00:00Z"), None),
        "may_2026": (pd.Timestamp("2026-05-01T00:00:00Z"), pd.Timestamp("2026-06-01T00:00:00Z")),
    }


def monthly_slices(frame: pd.DataFrame) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    ts = pd.DatetimeIndex(pd.to_datetime(frame["ts"], utc=True))
    starts = pd.date_range(ts[0].floor("D").replace(day=1), ts[-1].ceil("D"), freq="MS", tz="UTC")
    result: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    for start in starts:
        end = start + pd.offsets.MonthBegin(1)
        if end <= ts[0] or start >= ts[-1] + pd.Timedelta(hours=6):
            continue
        result.append((f"month_{start:%Y_%m}", pd.Timestamp(start), pd.Timestamp(end)))
    return result


def rolling_slices(frame: pd.DataFrame, days: int = 21) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    ts = pd.DatetimeIndex(pd.to_datetime(frame["ts"], utc=True))
    start = ts[0]
    end = ts[-1] + pd.Timedelta(hours=6)
    result: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    current = start
    while current < end:
        window_end = min(current + pd.Timedelta(days=days), end)
        result.append((f"rolling_{current:%Y%m%d_%H%M}", pd.Timestamp(current), pd.Timestamp(window_end)))
        current = window_end
    return result


def metrics_with_spec(spec: Rs4Spec, strategy: Any, slice_name: str, start: pd.Timestamp | None, end: pd.Timestamp | None) -> dict[str, Any]:
    row = base.metrics_for_returns(spec.name, strategy.frame, strategy.returns, strategy.positions, strategy.trades, start=start, end=end)
    row.update(
        {
            "strategy": spec.name,
            "group": spec.group,
            "changed_parameter": spec.changed_parameter,
            "changed_value": spec.changed_value,
            "slice": slice_name,
            "weight": spec.weight,
        }
    )
    return row


def build_report(
    baseline_full: dict[str, Any],
    ablation: pd.DataFrame,
    slices: pd.DataFrame,
    rolling: pd.DataFrame,
    specs: list[Rs4Spec],
) -> str:
    baseline_name = "baseline"
    full = ablation.set_index("strategy")
    baseline_return = float(baseline_full["total_return"])
    baseline_dd = float(baseline_full["max_drawdown"])
    baseline_worst_month = float(full.at[baseline_name, "worst_month_return"])
    baseline_worst_rolling = float(full.at[baseline_name, "worst_rolling21d_return"])

    failures = ablation[
        (ablation["total_return"] <= 0)
        | (ablation["max_drawdown"] <= -0.35)
        | (ablation["positive_months"] < 8)
    ].copy()
    dd_sensitive = ablation.sort_values("max_drawdown").head(8)
    best_returns = ablation.sort_values("total_return", ascending=False).head(8)
    group_summary = (
        ablation.groupby("group", as_index=False)
        .agg(
            variants=("strategy", "count"),
            min_total_return=("total_return", "min"),
            max_total_return=("total_return", "max"),
            worst_max_drawdown=("max_drawdown", "min"),
            min_positive_months=("positive_months", "min"),
            worst_rolling21d=("worst_rolling21d_return", "min"),
        )
        .sort_values(["worst_max_drawdown", "min_total_return"])
    )

    fixed_baseline = slices[slices["strategy"] == baseline_name]
    fixed_baseline = fixed_baseline[~fixed_baseline["slice"].str.startswith("month_")]

    def table_lines(frame: pd.DataFrame, columns: list[str], limit: int | None = None) -> list[str]:
        selected = frame.head(limit) if limit else frame
        lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
        for _, row in selected.iterrows():
            rendered = []
            for column in columns:
                value = row[column]
                if isinstance(value, float):
                    if "return" in column or "drawdown" in column:
                        rendered.append(pct(value))
                    else:
                        rendered.append(num(value))
                else:
                    rendered.append(str(value))
            lines.append("| " + " | ".join(rendered) + " |")
        return lines

    lines = [
        "# HYPE-6H-RS4 全参数消融与时间稳定性 2026-06-28",
        "",
        "Family id：`HYPE-6H-RS4-Regime-Switch`。本报告在 2026-06-26 独立复现脚本基础上做 one-at-a-time 参数消融，不做新参数搜索，不把更高分变体提升为候选。",
        "",
        "## 口径",
        "",
        f"- 数据与执行：沿用 Binance HYPEUSDT perpetual `5m` 聚合 `6h`、6h 收盘信号、下一根 6h 开盘成交、单边 `9.5bps` 成本与现有 funding 对齐口径。",
        f"- 消融数量：`{len(specs)}` 个配置，其中 `1` 个基线，`{len(specs) - 1}` 个单参数变体。",
        "- 稳定性：固定阶段切片、逐月切片、非重叠 21 天滚动窗口。",
        "- 注意：funding 仍只覆盖到 `2026-06-01`，之后 funding 按 0 处理；本报告不解决 Bybit 全史缺口。",
        "",
        "## 基线结果",
        "",
        f"- 全样本：收益 `{pct(baseline_return)}`，最大回撤 `{pct(baseline_dd)}`，Sharpe `{num(float(baseline_full['sharpe']))}`。",
        f"- 月度稳定性：正月份 `{int(full.at[baseline_name, 'positive_months'])}/{int(full.at[baseline_name, 'month_count'])}`，最差月 `{pct(baseline_worst_month)}`。",
        f"- 21 天稳定性：正窗口 `{int(full.at[baseline_name, 'positive_rolling21d'])}/{int(full.at[baseline_name, 'rolling21d_count'])}`，最差 21 天 `{pct(baseline_worst_rolling)}`。",
        "",
        "## 固定时间片",
        "",
        *table_lines(
            fixed_baseline,
            ["slice", "total_return", "max_drawdown", "trade_count", "exposure"],
        ),
        "",
        "## 最脆弱参数组",
        "",
        *table_lines(
            group_summary,
            ["group", "variants", "min_total_return", "max_total_return", "worst_max_drawdown", "min_positive_months", "worst_rolling21d"],
        ),
        "",
        "## 回撤最差的单参数变体",
        "",
        *table_lines(
            dd_sensitive,
            ["strategy", "group", "changed_parameter", "changed_value", "total_return", "max_drawdown", "positive_months", "worst_rolling21d_return"],
            limit=8,
        ),
        "",
        "## 收益最高但不可直接采纳的变体",
        "",
        *table_lines(
            best_returns,
            ["strategy", "group", "changed_parameter", "changed_value", "total_return", "max_drawdown", "positive_months", "worst_rolling21d_return"],
            limit=8,
        ),
        "",
        "## 稳定性结论",
        "",
    ]
    if not failures.empty:
        lines.append(
            f"- `{len(failures)}` 个单参数变体触发失败条件（收益 <=0、回撤 <=-35% 或正月份 <8），说明 RS4 不是宽参数平台。"
        )
    if group_summary.iloc[0]["group"] in {"er_gate", "er_threshold", "melt_side", "v10_range_gate", "v10_range_threshold"}:
        lines.append("- 最脆弱的区域集中在 regime/filter 类参数，尤其是 ER gate、方向限制或 range gate；这些不是可随意调的装饰参数。")
    lines.extend(
        [
            "- 基线能赚钱，但分月/21 天窗口仍有明显负段；它更像少数 regime 事件驱动的策略，而不是平滑稳定的全天候 alpha。",
            "- 收益更高的变体主要来自放松过滤或提高 melt 暴露，通常伴随更深回撤或更差窗口，不能作为反向调参理由。",
            "- 当前状态维持 `diagnostic only / not promoted`；若继续，应先补 Bybit 全史、完整 funding、交易所横测，再做 live runner 状态机审计。",
            "",
            "## 保留证据",
            "",
            f"- summary JSON：`{SUMMARY_JSON}`",
            f"- ablation CSV：`{ABLATION_CSV}`",
            f"- slice CSV：`{SLICE_CSV}`",
            f"- rolling 21d CSV：`{ROLLING_CSV}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAG_ROOT.mkdir(parents=True, exist_ok=True)

    frame_5m = base.load_5m_frame()
    funding = base.load_funding_rates()
    quality_5m = base.quality_checks_5m(frame_5m)
    bars_6h, quality_6h = base.resample_to_6h(frame_5m)

    specs = ablation_specs()
    fixed = fixed_slices(bars_6h)
    month_windows = monthly_slices(bars_6h)
    rolling_windows = rolling_slices(bars_6h)

    ablation_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []

    for spec in specs:
        frame = attach_features_for_spec(bars_6h, funding, spec)
        strategy = run_spec(frame, spec)
        full_row = metrics_with_spec(spec, strategy, "full", None, None)

        month_metrics = [metrics_with_spec(spec, strategy, name, start, end) for name, start, end in month_windows]
        rolling_metrics = [metrics_with_spec(spec, strategy, name, start, end) for name, start, end in rolling_windows]
        fixed_metrics = [metrics_with_spec(spec, strategy, name, start, end) for name, (start, end) in fixed.items()]

        month_returns = np.asarray([row["total_return"] for row in month_metrics], dtype=float)
        rolling_returns = np.asarray([row["total_return"] for row in rolling_metrics], dtype=float)
        full_row.update(
            {
                "month_count": int(len(month_metrics)),
                "positive_months": int(np.sum(month_returns > 0)),
                "worst_month_return": float(np.min(month_returns)) if len(month_returns) else 0.0,
                "median_month_return": float(np.median(month_returns)) if len(month_returns) else 0.0,
                "rolling21d_count": int(len(rolling_metrics)),
                "positive_rolling21d": int(np.sum(rolling_returns > 0)),
                "worst_rolling21d_return": float(np.min(rolling_returns)) if len(rolling_returns) else 0.0,
                "median_rolling21d_return": float(np.median(rolling_returns)) if len(rolling_returns) else 0.0,
                **{f"param_{key}": value for key, value in asdict(spec).items()},
            }
        )
        ablation_rows.append(full_row)
        slice_rows.extend(fixed_metrics)
        slice_rows.extend(month_metrics)
        rolling_rows.extend(rolling_metrics)

    ablation = pd.DataFrame(ablation_rows)
    slices = pd.DataFrame(slice_rows)
    rolling = pd.DataFrame(rolling_rows)

    baseline_full = ablation[ablation["strategy"] == "baseline"].iloc[0].to_dict()
    summary = {
        "strategy_family": "HYPE-6H-RS4-Regime-Switch",
        "status": "diagnostic_only_not_promoted",
        "ablation_style": "one_at_a_time_full_parameter_ablation",
        "spec_count": len(specs),
        "baseline": baseline_full,
        "quality_5m": quality_5m,
        "quality_6h": quality_6h,
        "funding": {
            "rows": int(len(funding)),
            "start_ts": str(funding["ts"].iloc[0]) if len(funding) else None,
            "end_ts": str(funding["ts"].iloc[-1]) if len(funding) else None,
        },
        "artifacts": {
            "summary_json": str(SUMMARY_JSON),
            "ablation_csv": str(ABLATION_CSV),
            "slice_csv": str(SLICE_CSV),
            "rolling_csv": str(ROLLING_CSV),
            "report_md": str(REPORT_MD),
        },
    }

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    ablation.to_csv(ABLATION_CSV, index=False)
    slices.to_csv(SLICE_CSV, index=False)
    rolling.to_csv(ROLLING_CSV, index=False)
    REPORT_MD.write_text(build_report(baseline_full, ablation, slices, rolling, specs), encoding="utf-8")
    print(json.dumps({"summary": str(SUMMARY_JSON), "report": str(REPORT_MD)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
