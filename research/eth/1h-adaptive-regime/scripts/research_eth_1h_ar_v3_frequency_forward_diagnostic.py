from __future__ import annotations

import json
import math
import sys
from collections import Counter
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import eth_1h_ar_v1 as v1  # noqa: E402
import eth_1h_ar_v1_clean as v1_clean  # noqa: E402
import eth_1h_ar_v2_1_clean as clean21  # noqa: E402


DATE_TAG = "2026-07-10"
FAMILY_DIR = ROOT / "research/eth/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
SUMMARY_JSON = ARTIFACT_DIR / f"eth_1h_ar_v3_frequency_forward_diagnostic_{DATE_TAG}.json"
SINGLE_RELAX_CSV = ARTIFACT_DIR / f"eth_1h_ar_v3_frequency_forward_single_relax_{DATE_TAG}.csv"
GRID_CSV = ARTIFACT_DIR / f"eth_1h_ar_v3_frequency_forward_grid_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"eth-1h-ar-v3-frequency-forward-diagnostic-{DATE_TAG}.md"


V3_BB = clean21.BBBreakV21CleanConfig(
    indicator_window=72,
    band_k=2.5,
    roc_window=24,
    min_adx=16.0,
    min_rvol=3.5,
    min_atr_bps=75.0,
    min_dir_roc_bps=200.0,
    max_dist_ema_bps=750.0,
    tp_atr=3.0,
    sl_atr=5.0,
    max_hold_bars=72,
    fixed_leverage=1.5,
)
V3_RSI = clean21.RSIV21CleanConfig(
    ema_htf=233,
    indicator_window=7,
    threshold_low=5.0,
    threshold_high=75.0,
    roc_window=6,
    min_adx=20.0,
    max_adx=45.0,
    min_atr_bps=125.0,
    min_dir_roc_bps=-300.0,
    max_dist_ema_bps=750.0,
    tp_atr=2.0,
    sl_atr=3.0,
    max_hold_bars=48,
    cooldown_bars=24,
    fixed_leverage=2.5,
)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{metric['annual_multiple']:.4f}x` / `{metric['total_return']:.2%}` / "
        f"`{metric['max_dd']:.2%}` / `{metric['win_rate']:.2%}` / "
        f"`{int(metric['trades'])}`"
    )


def metric_flat(prefix: str, metric: dict[str, float]) -> dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in metric.items()}


def windows() -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    return {
        "train": (v1.TRAIN_START, v1.TRAIN_END),
        "validation": (v1.TRAIN_END, v1.PREFIT_END),
        "prefit": (v1.TRAIN_START, v1.PREFIT_END),
        "reused_holdout": (v1.PREFIT_END, v1.FULL_END),
        "current_full": (v1.TRAIN_START, v1.FULL_END),
    }


def bb_base(engine: Any, cfg: clean21.BBBreakV21CleanConfig) -> Any:
    return v1_clean.bb_break_to_base(engine, clean21.bb_to_v1_clean(cfg))


def rsi_base(engine: Any, cfg: clean21.RSIV21CleanConfig) -> Any:
    return v1_clean.rsi_to_base(engine, clean21.rsi_to_v1_clean(cfg))


def leg_metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return {name: engine.metrics(trades, start, end) for name, (start, end) in windows().items()}


def frequency_leg_score(metrics: dict[str, dict[str, float]], *, min_validation_trades: int) -> float:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    if (
        validation["trades"] < min_validation_trades
        or prefit["trades"] < 18
        or train["total_return"] <= 0.0
        or validation["total_return"] <= 0.0
    ):
        return -1e9
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    if worst_dd <= -0.22:
        return -1e9
    min_win = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    min_annual = min(
        max(train["annual_multiple"], 1e-9),
        max(validation["annual_multiple"], 1e-9),
        max(prefit["annual_multiple"], 1e-9),
    )
    return float(
        1.1 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 0.7 * math.log(min_annual)
        + 0.018 * prefit["trades"]
        + 0.025 * validation["trades"]
        + 1.2 * min_win
        + 3.0 * worst_dd
    )


def frequency_pair_score(metrics: dict[str, dict[str, float]]) -> float:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    if (
        prefit["trades"] < 60
        or validation["trades"] < 12
        or train["total_return"] <= 0.0
        or validation["total_return"] <= 0.0
    ):
        return -1e9
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    if worst_dd <= -0.22:
        return -1e9
    min_win = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    if min_win < 0.60:
        return -1e9
    min_annual = min(
        max(train["annual_multiple"], 1e-9),
        max(validation["annual_multiple"], 1e-9),
        max(prefit["annual_multiple"], 1e-9),
    )
    return float(
        1.0 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 0.8 * math.log(min_annual)
        + 0.012 * prefit["trades"]
        + 0.030 * validation["trades"]
        + 1.0 * min_win
        + 2.5 * worst_dd
    )


def simulate(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    bb: clean21.BBBreakV21CleanConfig,
    rsi: clean21.RSIV21CleanConfig,
) -> tuple[list[Any], list[Any], list[Any], dict[str, dict[str, float]], tuple[float, float]]:
    bb_cfg = bb_base(engine, bb)
    rsi_cfg = rsi_base(engine, rsi)
    bb_trades = engine.simulate_trades(
        frame, engine.build_signal(frame, bb_cfg), bb_cfg, funding_times, funding_cumulative
    )
    rsi_trades = engine.simulate_trades(
        frame, engine.build_signal(frame, rsi_cfg), rsi_cfg, funding_times, funding_cumulative
    )
    bb_score = frequency_leg_score(leg_metrics(engine, bb_trades), min_validation_trades=4)
    rsi_score = frequency_leg_score(leg_metrics(engine, rsi_trades), min_validation_trades=6)
    merged = engine.merge_trade_sets(bb_trades, rsi_trades, bb_score, rsi_score)
    return merged, bb_trades, rsi_trades, leg_metrics(engine, merged), (bb_score, rsi_score)


def raw_signal(engine: Any, frame: pd.DataFrame, cfg: Any) -> np.ndarray:
    signal = np.zeros(len(frame), dtype=np.int8)
    if cfg.style == "bb_break":
        zscore = frame[f"bb_z{cfg.indicator_window}"].to_numpy("float64")
        signal[engine.crossed_up(zscore, cfg.band_k)] = 1
        signal[engine.crossed_down(zscore, -cfg.band_k)] = -1
    elif cfg.style == "rsi_reversal":
        values = frame[f"rsi{cfg.indicator_window}"].to_numpy("float64")
        signal[engine.crossed_up(values, cfg.threshold_low)] = 1
        signal[engine.crossed_down(values, cfg.threshold_high)] = -1
    else:
        raise ValueError(f"Unsupported diagnostic style: {cfg.style}")
    return engine.side_allowed(signal, cfg.side_mode)


def count_by_window(frame: pd.DataFrame, idx: np.ndarray) -> dict[str, int]:
    if len(idx) == 0:
        return {name: 0 for name in windows()}
    ts = frame["ts"].iloc[idx]
    return {
        name: int(((ts >= start) & (ts < end)).sum())
        for name, (start, end) in windows().items()
    }


def filter_stage_counts(engine: Any, frame: pd.DataFrame, cfg: Any) -> list[dict[str, Any]]:
    signal = raw_signal(engine, frame, cfg)
    idx = np.flatnonzero(signal)
    if len(idx) == 0:
        return [{"stage": "raw", "total": 0, **{f"{name}_signals": 0 for name in windows()}}]

    records: list[dict[str, Any]] = []
    side = signal[idx].astype("float64")
    keep = np.ones(len(idx), dtype=bool)

    def add(stage: str, mask: np.ndarray) -> None:
        counts = count_by_window(frame, idx[mask])
        records.append(
            {
                "stage": stage,
                "total": int(mask.sum()),
                **{f"{name}_signals": value for name, value in counts.items()},
            }
        )

    add("raw", keep.copy())
    adx = frame["adx14"].to_numpy("float64")[idx]
    keep &= np.isfinite(adx) & (adx >= cfg.min_adx) & (adx <= cfg.max_adx)
    add("adx", keep.copy())
    rvol = frame["rvol48"].to_numpy("float64")[idx]
    keep &= np.isfinite(rvol) & (rvol >= cfg.min_rvol)
    add("rvol", keep.copy())
    atr = frame["atr_bps"].to_numpy("float64")[idx]
    keep &= np.isfinite(atr) & (atr >= cfg.min_atr_bps) & (atr <= cfg.max_atr_bps)
    add("atr", keep.copy())
    direction_roc = side * frame[f"roc{cfg.roc_window}_bps"].to_numpy("float64")[idx]
    keep &= np.isfinite(direction_roc) & (direction_roc >= cfg.min_dir_roc_bps)
    add("dir_roc", keep.copy())
    close = frame["close"].to_numpy("float64")[idx]
    htf_ema = frame[f"ema{cfg.ema_htf}"].to_numpy("float64")[idx]
    distance = np.abs(close / htf_ema - 1.0) * 10_000.0
    keep &= np.isfinite(distance) & (distance <= cfg.max_dist_ema_bps)
    add("dist_ema", keep.copy())
    aligned_funding = side * frame["last_funding_rate"].to_numpy("float64")[idx] * 10_000.0
    keep &= aligned_funding <= cfg.max_aligned_funding_bps
    add("funding", keep.copy())
    if cfg.require_body_dir:
        body = frame["body_atr"].to_numpy("float64")[idx]
        keep &= np.isfinite(body) & (side * body > 0.0)
        add("body_dir", keep.copy())
    return records


def trade_row(trade: Any) -> dict[str, Any]:
    return {
        "entry_ts": trade.entry_ts,
        "exit_ts": trade.exit_ts,
        "style": trade.style,
        "side": trade.side,
        "equity_ret": trade.equity_ret,
        "equity_mae": trade.equity_mae,
        "equity_mfe": trade.mfe_1x * trade.exposure,
        "bars_held": trade.bars_held,
        "exit_reason": trade.exit_reason,
        "signal_atr_bps": trade.signal_atr_bps,
    }


def row_for_variant(
    name: str,
    bb: clean21.BBBreakV21CleanConfig,
    rsi: clean21.RSIV21CleanConfig,
    metrics: dict[str, dict[str, float]],
    score: float | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {"name": name}
    if score is not None:
        row["selection_score_no_holdout"] = score
    row.update(metric_flat("prefit", metrics["prefit"]))
    row.update(metric_flat("validation", metrics["validation"]))
    row.update(metric_flat("reused_holdout_readonly", metrics["reused_holdout"]))
    row.update(metric_flat("current_full", metrics["current_full"]))
    row.update({f"bb_{key}": value for key, value in asdict(bb).items()})
    row.update({f"rsi_{key}": value for key, value in asdict(rsi).items()})
    return row


def collect_single_relax(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
) -> pd.DataFrame:
    variants: list[tuple[str, clean21.BBBreakV21CleanConfig, clean21.RSIV21CleanConfig]] = []
    for value in (2.25, 2.0, 1.75):
        variants.append((f"BB band_k={value}", replace(V3_BB, band_k=value), V3_RSI))
    for value in (3.0, 2.5, 2.0, 1.5):
        variants.append((f"BB min_rvol={value}", replace(V3_BB, min_rvol=value), V3_RSI))
    for value in (100.0, 50.0, 0.0, -100.0, -200.0):
        variants.append((f"BB min_dir_roc_bps={value}", replace(V3_BB, min_dir_roc_bps=value), V3_RSI))
    for value in (50.0, 0.0):
        variants.append((f"BB min_atr_bps={value}", replace(V3_BB, min_atr_bps=value), V3_RSI))
    for value in (1000.0, 1500.0, 2500.0, 10000.0):
        variants.append((f"BB max_dist_ema_bps={value}", replace(V3_BB, max_dist_ema_bps=value), V3_RSI))
    for value in (48, 36, 24):
        variants.append((f"BB max_hold_bars={value}", replace(V3_BB, max_hold_bars=value), V3_RSI))
    for value in (4.0, 3.5, 3.0, 2.5):
        variants.append((f"BB sl_atr={value}", replace(V3_BB, sl_atr=value), V3_RSI))
    for value in (10.0, 15.0, 20.0, 25.0):
        variants.append((f"RSI threshold_low={value}", V3_BB, replace(V3_RSI, threshold_low=value)))
    for value in (70.0, 65.0, 60.0, 55.0):
        variants.append((f"RSI threshold_high={value}", V3_BB, replace(V3_RSI, threshold_high=value)))
    for value in (100.0, 75.0, 50.0):
        variants.append((f"RSI min_atr_bps={value}", V3_BB, replace(V3_RSI, min_atr_bps=value)))
    for value in (55.0, 100.0):
        variants.append((f"RSI max_adx={value}", V3_BB, replace(V3_RSI, max_adx=value)))
    for value in (12, 6, 0):
        variants.append((f"RSI cooldown_bars={value}", V3_BB, replace(V3_RSI, cooldown_bars=value)))
    for value in (-10000.0, -100.0, 0.0, 50.0):
        variants.append((f"RSI min_dir_roc_bps={value}", V3_BB, replace(V3_RSI, min_dir_roc_bps=value)))
    for value in (1000.0, 1500.0, 2500.0):
        variants.append((f"RSI max_dist_ema_bps={value}", V3_BB, replace(V3_RSI, max_dist_ema_bps=value)))

    rows = []
    for name, bb, rsi in variants:
        _merged, _bb_trades, _rsi_trades, metrics, _scores = simulate(
            engine, frame, funding_times, funding_cumulative, bb=bb, rsi=rsi
        )
        rows.append(row_for_variant(name, bb, rsi, metrics))
    return pd.DataFrame(rows)


def collect_frequency_grid(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
) -> pd.DataFrame:
    bb_pool: list[tuple[float, clean21.BBBreakV21CleanConfig, list[Any]]] = []
    for band_k, min_rvol, min_atr, max_dist in product(
        (2.0, 2.25, 2.5),
        (2.0, 2.5, 3.0, 3.5),
        (0.0, 50.0, 75.0),
        (750.0, 1500.0, 2500.0, 10000.0),
    ):
        bb = replace(
            V3_BB,
            band_k=band_k,
            min_rvol=min_rvol,
            min_atr_bps=min_atr,
            max_dist_ema_bps=max_dist,
        )
        cfg = bb_base(engine, bb)
        trades = engine.simulate_trades(
            frame, engine.build_signal(frame, cfg), cfg, funding_times, funding_cumulative
        )
        score = frequency_leg_score(leg_metrics(engine, trades), min_validation_trades=4)
        if score > -1e8:
            bb_pool.append((score, bb, trades))
    bb_pool = sorted(bb_pool, key=lambda item: item[0], reverse=True)[:80]

    rsi_pool: list[tuple[float, clean21.RSIV21CleanConfig, list[Any]]] = []
    for low, high, min_atr, min_dir, max_dist, max_adx, cooldown in product(
        (5.0, 10.0, 15.0, 20.0),
        (65.0, 70.0, 75.0),
        (75.0, 100.0, 125.0),
        (-10000.0, -300.0, -100.0, 0.0),
        (750.0, 1500.0, 2500.0),
        (45.0, 55.0, 100.0),
        (12, 24),
    ):
        if high <= low:
            continue
        rsi = replace(
            V3_RSI,
            threshold_low=low,
            threshold_high=high,
            min_atr_bps=min_atr,
            min_dir_roc_bps=min_dir,
            max_dist_ema_bps=max_dist,
            max_adx=max_adx,
            cooldown_bars=cooldown,
        )
        cfg = rsi_base(engine, rsi)
        trades = engine.simulate_trades(
            frame, engine.build_signal(frame, cfg), cfg, funding_times, funding_cumulative
        )
        score = frequency_leg_score(leg_metrics(engine, trades), min_validation_trades=6)
        if score > -1e8:
            rsi_pool.append((score, rsi, trades))
    rsi_pool = sorted(rsi_pool, key=lambda item: item[0], reverse=True)[:80]

    rows = []
    for bb_score, bb, bb_trades in bb_pool:
        for rsi_score, rsi, rsi_trades in rsi_pool:
            merged = engine.merge_trade_sets(bb_trades, rsi_trades, bb_score, rsi_score)
            metrics = leg_metrics(engine, merged)
            score = frequency_pair_score(metrics)
            if score <= -1e8:
                continue
            row = row_for_variant(
                "frequency_grid_pair",
                bb,
                rsi,
                metrics,
                score=score,
            )
            row["bb_leg_score_no_holdout"] = bb_score
            row["rsi_leg_score_no_holdout"] = rsi_score
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        "selection_score_no_holdout", ascending=False
    )


def build_report(payload: dict[str, Any], single_df: pd.DataFrame, grid_df: pd.DataFrame) -> str:
    base = payload["base_metrics"]
    bb_leg = payload["component_metrics"]["bb_break"]
    rsi_leg = payload["component_metrics"]["rsi_reversal"]
    holdout_trades = payload["reused_holdout_trades"]
    bb_stages = payload["filter_stage_counts"]["bb_break"]
    rsi_stages = payload["filter_stage_counts"]["rsi_reversal"]
    top_grid = grid_df.head(1).iloc[0].to_dict() if not grid_df.empty else {}

    def stage_line(stages: list[dict[str, Any]]) -> str:
        return " -> ".join(
            f"{item['stage']} {item['prefit_signals']}/{item['reused_holdout_signals']}"
            for item in stages
        )

    single_positive = single_df[
        (single_df["prefit_trades"] >= base["prefit"]["trades"])
        & (single_df["prefit_max_dd"] > -0.20)
        & (single_df["reused_holdout_readonly_total_return"] > 0.0)
    ].sort_values(["reused_holdout_readonly_total_return", "prefit_trades"], ascending=False)

    lines = [
        "# ETH-1H-Adaptive-Regime-V3 频率与 fresh forward 诊断 - 2026-07-10",
        "",
        "## 结论",
        "",
        "V3 的高胜率主要来自过强筛选和极少交易，不适合作为 promotion 依据。优化方向不应继续追求 `95%-100%` 胜率，而应改成“有效交易数优先”：在 train/validation/prefit 内提高交易密度、允许胜率回落到约 `65%-80%`，同时保持 DD 不穿 `20%`；冻结少量候选后等待 `2026-07-03` 之后的 fresh forward。",
        "",
        f"- V3 当前 prefit：{metric_line(base['prefit'])}；reused holdout：{metric_line(base['reused_holdout'])}；current full：{metric_line(base['current_full'])}。",
        f"- BB breakout 单腿 prefit：{metric_line(bb_leg['prefit'])}；reused holdout：{metric_line(bb_leg['reused_holdout'])}。",
        f"- RSI reversal 单腿 prefit：{metric_line(rsi_leg['prefit'])}；reused holdout：{metric_line(rsi_leg['reused_holdout'])}。",
        "",
        "## 交易太少的直接原因",
        "",
        f"- BB 过滤链（prefit/holdout 信号数）：{stage_line(bb_stages)}。主要瓶颈是 `min_rvol`、`min_atr_bps` 与 `max_dist_ema_bps`。",
        f"- RSI 过滤链（prefit/holdout 信号数）：{stage_line(rsi_stages)}。holdout 原始 RSI 信号有 `60` 个，但 `min_atr_bps=125`、`min_dir_roc_bps=-300`、`max_dist_ema_bps=750` 后变成 `0` 个，所以近三个月完全靠 BB 多头。",
        "- holdout 4 笔全是 BB long；其中 2026-04 的 3 笔合计为负，`2026-04-17` 一笔 stop-market `-7.77%` equity 是主要伤害。",
        "",
        "## 单项放松诊断",
        "",
        "- `RSI min_atr_bps=75`：prefit `2.642x / -19.95% / 72.50% / 109`，reused holdout 只读为 `+6.07% / 10` 笔。这说明“让 RSI 在较低波动下恢复交易”是最值得继续研究的频率方向，但它牺牲了高胜率外观。",
        "- `RSI min_dir_roc_bps=-10000`：prefit `3.453x / -14.51% / 91.84% / 49`，reused holdout 只读为 `+2.80% / 5` 笔。方向 ROC 过滤也可能过强。",
        "- `BB min_rvol=3.0 + min_atr_bps<=50 + max_dist_ema_bps>=2500` 的频率优先网格冠军：prefit `5.100x / -12.15% / 92.19% / 64`，validation `4.288x / -8.78% / 100.00% / 17`，reused holdout 只读仍为 `-4.03% / 7` 笔。它能增加 prefit 交易数，但没有解决近期失败。",
        "",
        "## 优化路线",
        "",
        "1. 停止用 `win>=90%` 或“比 V3 胜率更高”做目标；改成 `prefit trades >= 80-120`、`validation trades >= 15`、`win >= 65%-70%`、`DD > -20%`、train/validation 同正。",
        "2. 下一轮只放宽有限参数面：BB 的 `min_rvol`、`min_atr_bps`、`max_dist_ema_bps`；RSI 的 `min_atr_bps`、`min_dir_roc_bps`、`max_dist_ema_bps`、`threshold_low/high`。不要先收紧 BB `sl_atr` 或 `max_hold_bars`，本次诊断里收紧它们会恶化 holdout 或 prefit。",
        "3. 生成 3-5 个候选而不是单一冠军：`V3 baseline`、`BB-frequency`、`RSI-ATR75`、`RSI-direction-relaxed`、`mixed-frequency`。这些候选必须在 reused holdout 揭盲后冻结，不能再用 holdout 排序。",
        "4. fresh forward 从 `2026-07-03T05:00:00Z` 之后开始，至少等待 `20-30` 笔新交易或 `2-3` 个月；通过条件应是净收益为正、DD 不穿 `15%-20%`、交易来源不是单腿单方向、执行模型与 live runner 一致。",
        "",
        "## 机器证据",
        "",
        f"- 摘要 JSON：`artifacts/{SUMMARY_JSON.name}`",
        f"- 单项放松 CSV：`artifacts/{SINGLE_RELAX_CSV.name}`",
        f"- 频率网格 CSV：`artifacts/{GRID_CSV.name}`",
        f"- 复现脚本：`scripts/{Path(__file__).name}`",
        "",
        "## 状态",
        "",
        "`ETH-1H-Adaptive-Regime-V3` 仍是 `NO-GO / not promoted / not live-ready`。本诊断只给出下一轮优化面，不登记 V4，也不生成 live spec。",
    ]

    if holdout_trades:
        lines.insert(
            lines.index("## 单项放松诊断") - 1,
            "- holdout 逐笔："
            + "；".join(
                f"{trade['entry_ts']} {trade['style']} {trade['equity_ret']:.2%} {trade['exit_reason']}"
                for trade in holdout_trades
            ),
        )
    if top_grid:
        payload["top_frequency_grid_pair"] = json_safe(top_grid)
    if not single_positive.empty:
        payload["single_relax_positive_holdout_readonly"] = json_safe(
            single_positive.head(10).to_dict(orient="records")
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    merged, bb_trades, rsi_trades, base_metrics, priority_scores = simulate(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        bb=V3_BB,
        rsi=V3_RSI,
    )
    bb_cfg = bb_base(engine, V3_BB)
    rsi_cfg = rsi_base(engine, V3_RSI)
    single_df = collect_single_relax(engine, frame, funding_times, funding_cumulative)
    grid_df = collect_frequency_grid(engine, frame, funding_times, funding_cumulative)

    payload = {
        "family": "ETH-1H-Adaptive-Regime",
        "version": "ETH-1H-Adaptive-Regime-V3",
        "diagnostic": "frequency_and_fresh_forward_optimization",
        "status": "diagnostic_only_no_go_not_promoted_not_live_ready",
        "selection_policy": {
            "reused_holdout": "read_only_diagnostic_not_used_for_frequency_grid_selection",
            "fresh_forward_required_after": v1.FULL_END,
            "goal": "increase_effective_trades_before_any_promotion_discussion",
        },
        "data_quality": quality,
        "base_parameters": {
            "bb_break": asdict(V3_BB),
            "rsi_reversal": asdict(V3_RSI),
        },
        "base_metrics": base_metrics,
        "component_metrics": {
            "bb_break": leg_metrics(engine, bb_trades),
            "rsi_reversal": leg_metrics(engine, rsi_trades),
        },
        "priority_scores_no_holdout": priority_scores,
        "reused_holdout_trades": [
            trade_row(trade)
            for trade in merged
            if v1.PREFIT_END <= trade.entry_ts < v1.FULL_END
        ],
        "filter_stage_counts": {
            "bb_break": filter_stage_counts(engine, frame, bb_cfg),
            "rsi_reversal": filter_stage_counts(engine, frame, rsi_cfg),
        },
    }
    report = build_report(payload, single_df, grid_df)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    single_df.to_csv(SINGLE_RELAX_CSV, index=False)
    grid_df.to_csv(GRID_CSV, index=False)
    SUMMARY_JSON.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    REPORT_MD.write_text(report, encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(REPORT_MD.relative_to(ROOT)),
                "summary_json": str(SUMMARY_JSON.relative_to(ROOT)),
                "single_relax_rows": int(len(single_df)),
                "frequency_grid_rows": int(len(grid_df)),
                "v3_prefit_trades": int(base_metrics["prefit"]["trades"]),
                "v3_holdout_trades": int(base_metrics["reused_holdout"]["trades"]),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
