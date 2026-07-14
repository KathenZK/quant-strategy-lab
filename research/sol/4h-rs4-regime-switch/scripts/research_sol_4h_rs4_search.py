from __future__ import annotations

import importlib.util
import json
import math
import random
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/sol/4h-rs4-regime-switch"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
SOURCE_1H = (
    ROOT
    / "research/sol/1h-volatility-compression-breakout/artifacts"
    / "sol_binance_1h_closed_klines_2y.parquet"
)
SOURCE_QUALITY = (
    ROOT
    / "research/sol/1h-volatility-compression-breakout/artifacts"
    / "sol_binance_1h_data_quality_2y.json"
)
FUNDING_PATH = (
    ROOT
    / "data/normalized/funding/exchange=binance/market_type=perp"
    / "symbol=sol_usdt_usdt/funding.parquet"
)
ABLATION_PATH = (
    ROOT
    / "research/hype/6h-rs4-regime-switch/scripts"
    / "research_hype_6h_rs4_parameter_ablation.py"
)

DATE_TAG = "2026-07-13"
SUMMARY_JSON = ARTIFACT_DIR / f"sol_4h_rs4_search_{DATE_TAG}.json"
RANKING_CSV = ARTIFACT_DIR / f"sol_4h_rs4_search_ranking_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"sol_4h_rs4_search_slices_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"sol_4h_rs4_search_selected_trades_{DATE_TAG}.csv"
INPUT_4H = ARTIFACT_DIR / f"sol_4h_rs4_input_{DATE_TAG}.parquet"
QUALITY_4H = ARTIFACT_DIR / f"sol_4h_rs4_data_quality_{DATE_TAG}.json"
REPORT_MD = DIAGNOSTIC_DIR / f"sol-4h-rs4-search-{DATE_TAG}.md"

TRAIN_START = pd.Timestamp("2024-08-27T08:00:00Z")
TRAIN_END = pd.Timestamp("2025-09-10T19:48:00Z")
PREFIT_END = pd.Timestamp("2026-04-03T04:00:00Z")
REUSED_HOLDOUT_END = pd.Timestamp("2026-07-03T04:00:00Z")
FULL_END = pd.Timestamp("2026-07-13T04:00:00Z")

FEE_PER_FILL = 0.001
SLIPPAGE_PER_FILL = 0.0004
ONE_WAY_COST = FEE_PER_FILL + SLIPPAGE_PER_FILL
TARGET_ANNUAL_MULTIPLE = 10.0
TARGET_WIN_RATE = 0.80
TARGET_MAX_DD = -0.20

STANDARD_SLICES = (
    ("last_1d", pd.Timedelta(days=1)),
    ("last_7d", pd.Timedelta(days=7)),
    ("last_1m", pd.Timedelta(days=30)),
    ("last_3m", pd.Timedelta(days=91)),
    ("last_6m", pd.Timedelta(days=182)),
    ("last_1y", pd.Timedelta(days=365)),
)


@dataclass(slots=True)
class Candidate:
    spec: Any
    strategy: Any
    score: float
    metrics: dict[str, dict[str, float]]
    base_gate: bool
    hard_pass: bool


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_and_resample() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if not SOURCE_1H.exists() or not SOURCE_QUALITY.exists() or not FUNDING_PATH.exists():
        raise FileNotFoundError(
            "Run SOL-1H-VCB data fetch before the SOL-4H-RS4 search."
        )
    source = pd.read_parquet(SOURCE_1H)
    source["ts"] = pd.to_datetime(source["ts"], utc=True)
    source = (
        source.drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    source_quality = json.loads(SOURCE_QUALITY.read_text(encoding="utf-8"))
    if int(source_quality["data_quality"]["blocker_count"]) != 0:
        raise RuntimeError("Source 1h data has quality blockers")
    source["bar_ts"] = source["ts"].dt.floor("4h")
    grouped = source.groupby("bar_ts", sort=True)
    bars = grouped.agg(
        ts=("bar_ts", "first"),
        first_ts=("ts", "first"),
        last_ts=("ts", "last"),
        row_count=("ts", "size"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        quote_volume=("quote_volume", "sum"),
        trade_count=("trade_count", "sum"),
    ).reset_index(drop=True)
    bars = bars.loc[bars["row_count"] == 4].reset_index(drop=True)
    expected = pd.date_range(bars["ts"].iloc[0], bars["ts"].iloc[-1], freq="4h")
    missing = expected.difference(pd.DatetimeIndex(bars["ts"]))
    violations = {
        "missing_4h_bars": int(len(missing)),
        "duplicate_4h_bars": int(bars["ts"].duplicated().sum()),
        "row_count_not_4": int((bars["row_count"] != 4).sum()),
        "high_lt_open_close": int(
            (bars["high"] < bars[["open", "close"]].max(axis=1)).sum()
        ),
        "low_gt_open_close": int(
            (bars["low"] > bars[["open", "close"]].min(axis=1)).sum()
        ),
        "nonpositive_ohlc": int(
            ((bars[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum()
        ),
    }
    if sum(violations.values()):
        raise RuntimeError(f"4h data-quality blockers: {violations}")
    if bars["ts"].iloc[-1] + pd.Timedelta(hours=4) != FULL_END:
        raise RuntimeError(f"Unexpected 4h end: {bars['ts'].iloc[-1]}")

    funding = pd.read_parquet(FUNDING_PATH)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = (
        funding.drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    if funding.empty or funding["funding_rate"].isna().any():
        raise RuntimeError("Funding history missing or contains nulls")
    quality = {
        "source_1h": str(SOURCE_1H.relative_to(ROOT)),
        "source_quality": str(SOURCE_QUALITY.relative_to(ROOT)),
        "source_rows": int(len(source)),
        "rows_4h": int(len(bars)),
        "first_ts": bars["ts"].iloc[0].isoformat(),
        "last_ts": bars["ts"].iloc[-1].isoformat(),
        "violations": violations,
        "funding_rows": int(len(funding)),
        "funding_first_ts": funding["ts"].iloc[0].isoformat(),
        "funding_last_ts": funding["ts"].iloc[-1].isoformat(),
    }
    return bars, funding, quality


def attach_features(
    bars: pd.DataFrame, funding: pd.DataFrame, spec: Any
) -> pd.DataFrame:
    frame = bars.copy()
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    frame["range"] = (
        high.rolling(spec.range_window).max()
        / low.rolling(spec.range_window).min()
        - 1.0
    )
    ema_fast = close.ewm(
        span=spec.macd_fast, adjust=False, min_periods=spec.macd_fast
    ).mean()
    ema_slow = close.ewm(
        span=spec.macd_slow, adjust=False, min_periods=spec.macd_slow
    ).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(
        span=spec.macd_signal, adjust=False, min_periods=spec.macd_signal
    ).mean()
    frame["macd_hist"] = macd - macd_signal
    positive = frame["macd_hist"] > 0
    frame["macd_long_ok"] = (
        positive.rolling(spec.long_persist).sum() >= spec.long_persist
    )
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
    frame["hi_entry_prev"] = (
        high.shift(1).rolling(spec.donchian_entry).max()
    )
    frame["lo_entry_prev"] = low.shift(1).rolling(spec.donchian_entry).min()
    frame["hi_exit_prev"] = high.shift(1).rolling(spec.donchian_exit).max()
    frame["lo_exit_prev"] = low.shift(1).rolling(spec.donchian_exit).min()
    frame["open_ret_next"] = frame["open"].shift(-1) / frame["open"] - 1.0
    local_funding = funding.copy()
    local_funding["bar_ts"] = local_funding["ts"].dt.floor("4h")
    funding_sum = local_funding.groupby("bar_ts")["funding_rate"].sum()
    frame["funding_sum"] = (
        frame["ts"].map(funding_sum).fillna(0.0).astype(float)
    )
    return frame


def shift_positions(positions: np.ndarray, extra_bars: int) -> np.ndarray:
    if extra_bars <= 0:
        return positions.copy()
    shifted = np.zeros_like(positions)
    shifted[extra_bars:] = positions[:-extra_bars]
    return shifted


def run_spec(
    abl: Any,
    frame: pd.DataFrame,
    spec: Any,
    *,
    extra_delay_bars: int = 0,
) -> Any:
    v10_positions = shift_positions(
        abl.simulate_v10(frame, spec), extra_delay_bars
    )
    melt_positions = shift_positions(
        abl.simulate_melt(frame, spec), extra_delay_bars
    )
    v10 = abl.leg_returns("v10", frame, v10_positions, spec)
    melt = abl.leg_returns("melt", frame, melt_positions, spec)
    return abl.base.StrategyReturns(
        name=spec.name,
        frame=frame,
        positions=v10.positions + spec.weight * melt.positions,
        returns=v10.returns + spec.weight * melt.returns,
        trades=[*v10.trades, *melt.trades],
    )


def metrics(
    strategy: Any,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, float]:
    ts = pd.DatetimeIndex(pd.to_datetime(strategy.frame["ts"], utc=True))
    mask = (ts >= start) & (ts < end)
    returns = np.asarray(strategy.returns, dtype="float64")[mask]
    days = max((end - start).total_seconds() / 86_400.0, 1.0)
    if not len(returns):
        returns = np.array([0.0])
    equity = np.cumprod(1.0 + np.nan_to_num(returns, nan=0.0))
    final_equity = float(equity[-1])
    peak = np.maximum.accumulate(np.r_[1.0, equity])
    drawdowns = np.r_[1.0, equity] / peak - 1.0
    annual_multiple = (
        final_equity ** (365.25 / days) if final_equity > 0.0 else 0.0
    )
    selected_trades = [
        trade
        for trade in strategy.trades
        if start <= pd.Timestamp(trade["entry_ts"]) < end
    ]
    trade_returns = np.array(
        [float(trade["net_return"]) for trade in selected_trades],
        dtype="float64",
    )
    positives = trade_returns[trade_returns > 0.0]
    negatives = -trade_returns[trade_returns < 0.0]
    positions = np.asarray(strategy.positions, dtype="float64")[mask]
    return {
        "days": float(days),
        "final_equity": final_equity,
        "total_return": final_equity - 1.0,
        "annual_multiple": float(annual_multiple),
        "max_dd": float(drawdowns.min()),
        "trade_count": float(len(selected_trades)),
        "win_rate": (
            float(len(positives) / len(trade_returns))
            if len(trade_returns)
            else 0.0
        ),
        "profit_factor": (
            float(positives.sum() / negatives.sum())
            if len(negatives)
            else math.inf if len(positives) else 0.0
        ),
        "avg_exposure": float(np.mean(np.abs(positions))) if len(positions) else 0.0,
        "max_exposure": float(np.max(np.abs(positions))) if len(positions) else 0.0,
    }


def window_metrics(strategy: Any) -> dict[str, dict[str, float]]:
    return {
        "train": metrics(strategy, TRAIN_START, TRAIN_END),
        "validation": metrics(strategy, TRAIN_END, PREFIT_END),
        "prefit": metrics(strategy, TRAIN_START, PREFIT_END),
        "reused_holdout": metrics(
            strategy, PREFIT_END, REUSED_HOLDOUT_END
        ),
        "fresh_forward": metrics(
            strategy, REUSED_HOLDOUT_END, FULL_END
        ),
        "current_full": metrics(strategy, TRAIN_START, FULL_END),
    }


def score_candidate(
    strategy: Any,
) -> tuple[float, dict[str, dict[str, float]], bool, bool]:
    windows = window_metrics(strategy)
    train = windows["train"]
    validation = windows["validation"]
    prefit = windows["prefit"]
    base_gate = bool(
        train["trade_count"] >= 8
        and validation["trade_count"] >= 4
        and prefit["trade_count"] >= 15
        and train["total_return"] > 0.0
        and validation["total_return"] > 0.0
        and min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
        > TARGET_MAX_DD
    )
    min_ann = min(train["annual_multiple"], validation["annual_multiple"])
    score = (
        1.0 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 1.3 * math.log(max(min_ann, 1e-9))
        + 0.20 * min(prefit["profit_factor"], 5.0)
        + 0.15 * min(prefit["trade_count"] / 20.0, 2.0)
        - 12.0
        * max(
            0.0,
            -0.20
            - min(train["max_dd"], validation["max_dd"], prefit["max_dd"]),
        )
        - 4.0 * int(train["total_return"] <= 0.0)
        - 6.0 * int(validation["total_return"] <= 0.0)
        - 2.0 * max(0.0, prefit["max_exposure"] - 2.0)
    )
    hard_pass = bool(
        base_gate
        and prefit["annual_multiple"] >= TARGET_ANNUAL_MULTIPLE
        and prefit["win_rate"] >= TARGET_WIN_RATE
        and prefit["max_dd"] > TARGET_MAX_DD
        and validation["total_return"] > 0.0
    )
    if base_gate:
        score += 2.0
    if hard_pass:
        score += 10.0
    return float(score), windows, base_gate, hard_pass


def random_spec(abl: Any, rng: random.Random, index: int) -> Any:
    macd = rng.choice(((8, 21, 5), (12, 26, 9)))
    return abl.Rs4Spec(
        name=f"SOL_4H_RS4_R{index:04d}",
        group="small_matrix",
        changed_parameter="multi",
        changed_value=str(index),
        range_window=rng.choice((8, 12, 16)),
        range_threshold=rng.choice((0.08, 0.12, 0.16)),
        macd_fast=macd[0],
        macd_slow=macd[1],
        macd_signal=macd[2],
        long_persist=rng.choice((1, 2, 3)),
        atr_window=rng.choice((14, 28)),
        use_mfeu=True,
        mfe_trigger_atr=rng.choice((1.5, 2.0, 2.5)),
        mfe_giveback_atr=rng.choice((1.0, 1.5, 2.0)),
        first_flat_exemption=False,
        breakeven_guard=False,
        er_window=rng.choice((14, 20, 30)),
        er_threshold=rng.choice((0.25, 0.35, 0.45)),
        donchian_entry=rng.choice((12, 20, 30)),
        donchian_exit=rng.choice((6, 10, 15)),
        melt_side_mode=rng.choice(("long", "both")),
        weight=rng.choice((0.5, 1.0)),
        cost_multiplier=1.0,
        use_funding=True,
    )


def spec_key(spec: Any) -> tuple[Any, ...]:
    values = asdict(spec)
    return tuple(
        value
        for key, value in values.items()
        if key not in {"name", "group", "changed_parameter", "changed_value"}
    )


def candidate_row(candidate: Candidate) -> dict[str, Any]:
    row: dict[str, Any] = {
        **{f"spec_{key}": value for key, value in asdict(candidate.spec).items()},
        "score": candidate.score,
        "base_gate": candidate.base_gate,
        "hard_pass": candidate.hard_pass,
    }
    for window, values in candidate.metrics.items():
        row.update({f"{window}_{key}": value for key, value in values.items()})
    return row


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def pct(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.2%}"


def mult(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.4f}x"


def main() -> None:
    rng = random.Random(20260713)
    abl = load_module(ABLATION_PATH, "sol_4h_rs4_ablation")
    abl.base.ONE_WAY_COST = ONE_WAY_COST
    bars, funding, quality = load_and_resample()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    bars.to_parquet(INPUT_4H, index=False)
    QUALITY_4H.write_text(
        json.dumps(quality, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    specs = [
        replace(
            abl.Rs4Spec(),
            name="SOL_4H_RS4_CANONICAL",
            first_flat_exemption=False,
            breakeven_guard=False,
            cost_multiplier=1.0,
        )
    ]
    seen = {spec_key(specs[0])}
    while len(specs) < 401:
        spec = random_spec(abl, rng, len(specs))
        key = spec_key(spec)
        if key not in seen:
            seen.add(key)
            specs.append(spec)

    candidates: list[Candidate] = []
    evaluated = 0
    base_gate_passes = 0
    hard_passes = 0
    for spec in specs:
        frame = attach_features(bars, funding, spec)
        strategy = run_spec(abl, frame, spec)
        score, windows, base_gate, hard_pass = score_candidate(strategy)
        evaluated += 1
        base_gate_passes += int(base_gate)
        hard_passes += int(hard_pass)
        candidates.append(
            Candidate(spec, strategy, score, windows, base_gate, hard_pass)
        )
    candidates.sort(
        key=lambda item: (item.hard_pass, item.base_gate, item.score),
        reverse=True,
    )
    if not candidates:
        raise RuntimeError("No SOL 4h RS4 spec survived prefit gates")
    selected = candidates[0]
    pd.DataFrame([candidate_row(item) for item in candidates]).to_csv(
        RANKING_CSV, index=False
    )
    pd.DataFrame(selected.strategy.trades).to_csv(TRADES_CSV, index=False)
    slices = [
        {
            "window": name,
            **metrics(selected.strategy, FULL_END - delta, FULL_END),
        }
        for name, delta in STANDARD_SLICES
    ]
    pd.DataFrame(slices).to_csv(SLICES_CSV, index=False)

    scenarios: list[dict[str, Any]] = []
    for name, extra_delay, cost_multiplier in (
        ("base_k1_cost1", 0, 1.0),
        ("delay_k2_cost1", 1, 1.0),
        ("base_k1_cost2", 0, 2.0),
    ):
        scenario_spec = replace(
            selected.spec,
            name=name,
            cost_multiplier=cost_multiplier,
        )
        frame = attach_features(bars, funding, scenario_spec)
        strategy = run_spec(
            abl,
            frame,
            scenario_spec,
            extra_delay_bars=extra_delay,
        )
        scenarios.append(
            {"scenario": name, "metrics": window_metrics(strategy)}
        )

    payload = {
        "family": "SOL-4H-RS4-Regime-Switch",
        "family_id": "SOL-4H-RS4",
        "status": "explore_not_promoted_not_live_ready",
        "selection_policy": {
            "uses": "train_validation_prefit_only",
            "reused_holdout": "audit_after_freeze_not_used_for_selection",
            "fresh_forward": "2026-07-03_to_2026-07-13_observation_only",
        },
        "targets": {
            "annual_multiple": TARGET_ANNUAL_MULTIPLE,
            "win_rate": TARGET_WIN_RATE,
            "max_drawdown_strictly_greater_than": TARGET_MAX_DD,
        },
        "costs": {
            "fee_per_fill": FEE_PER_FILL,
            "slippage_per_fill": SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_mapped_to_4h",
        },
        "data_quality": quality,
        "counts": {
            "specs": len(specs),
            "evaluated": evaluated,
            "base_gate_pass": base_gate_passes,
            "prefit_hard_pass": hard_passes,
        },
        "selected": candidate_row(selected),
        "top_20": [candidate_row(item) for item in candidates[:20]],
        "slices": slices,
        "scenarios": scenarios,
        "execution_blocker": (
            "RS4 position-return model has no exchange-resting intrabar "
            "protection stop; diagnostic only."
        ),
    }
    SUMMARY_JSON.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    windows = selected.metrics
    lines = [
        "# SOL-4H-RS4-Regime-Switch 首轮搜索 - 2026-07-13",
        "",
        "## 结论",
        "",
        (
            "至少一个 prefit spec 命中 `10x / 80% / <20% DD`，但 RS4 当前无 intrabar protection stop 且 fresh forward 太短，仍不得 promotion。"
            if hard_passes
            else "没有 prefit spec 命中 `10x / 80% / <20% DD`；本轮状态为 `explore / not promoted / not live-ready`。"
        ),
        "",
        f"- specs `{len(specs)}`；base-gate pass `{base_gate_passes}`；prefit hard pass `{hard_passes}`。",
        "- 机制：压缩 regime 的 MACD 双向 v10 leg，与扩张/高 ER regime 的 Donchian melt leg 互斥路由。",
        "",
        "## 数据与执行",
        "",
        f"- SOLUSDT perpetual `4h`：`{quality['rows_4h']}` 根完整 K，UTC `{quality['first_ts']}` 至 `{quality['last_ts']}`。",
        f"- 4h violations：`{quality['violations']}`。",
        "- fee `0.001`/fill，slippage `4 bps`/fill，逐 bar 计真实 funding。",
        "- 闭合 4h K 决策，下一根 4h open 生效。",
        "- blocker：当前 RS4 是 open-to-open position return 模型，没有交易所驻留的 intrabar protection stop；任何正收益也只能 diagnostic。",
        "",
        "## Prefit-only 选中观察",
        "",
        f"- id：`{selected.spec.name}`；score `{selected.score:.3f}`。",
        f"- train：annual `{mult(windows['train']['annual_multiple'])}`，DD `{pct(windows['train']['max_dd'])}`，win `{pct(windows['train']['win_rate'])}`，trades `{int(windows['train']['trade_count'])}`。",
        f"- validation：annual `{mult(windows['validation']['annual_multiple'])}`，DD `{pct(windows['validation']['max_dd'])}`，win `{pct(windows['validation']['win_rate'])}`，trades `{int(windows['validation']['trade_count'])}`。",
        f"- prefit：annual `{mult(windows['prefit']['annual_multiple'])}`，DD `{pct(windows['prefit']['max_dd'])}`，win `{pct(windows['prefit']['win_rate'])}`，trades `{int(windows['prefit']['trade_count'])}`。",
        f"- reused holdout：annual `{mult(windows['reused_holdout']['annual_multiple'])}`，return `{pct(windows['reused_holdout']['total_return'])}`，DD `{pct(windows['reused_holdout']['max_dd'])}`，win `{pct(windows['reused_holdout']['win_rate'])}`，trades `{int(windows['reused_holdout']['trade_count'])}`。",
        f"- fresh forward：return `{pct(windows['fresh_forward']['total_return'])}`，DD `{pct(windows['fresh_forward']['max_dd'])}`，trades `{int(windows['fresh_forward']['trade_count'])}`。",
        f"- current full：annual `{mult(windows['current_full']['annual_multiple'])}`，DD `{pct(windows['current_full']['max_dd'])}`，win `{pct(windows['current_full']['win_rate'])}`，trades `{int(windows['current_full']['trade_count'])}`。",
        "",
        "## 标准近期分片（锚定数据集末端，仅审计）",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in slices:
        lines.append(
            f"| `{row['window']}` | `{mult(row['annual_multiple'])}` | "
            f"`{pct(row['total_return'])}` | `{pct(row['max_dd'])}` | "
            f"`{pct(row['win_rate'])}` | `{int(row['trade_count'])}` | "
            f"`{row['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## 延迟与成本压力",
            "",
            "| Scenario | Prefit ann | Prefit DD | Holdout ann | Fresh return | Full ann | Full DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for scenario in scenarios:
        item = scenario["metrics"]
        lines.append(
            f"| `{scenario['scenario']}` | "
            f"`{mult(item['prefit']['annual_multiple'])}` | "
            f"`{pct(item['prefit']['max_dd'])}` | "
            f"`{mult(item['reused_holdout']['annual_multiple'])}` | "
            f"`{pct(item['fresh_forward']['total_return'])}` | "
            f"`{mult(item['current_full']['annual_multiple'])}` | "
            f"`{pct(item['current_full']['max_dd'])}` |"
        )
    lines.extend(
        [
            "",
            "## 研究边界",
            "",
            "- 本 family 与 HYPE-RS4、SOL-1H-AR 独立，不继承版本号。",
            "- reused holdout 不参与选择；fresh forward 仅约 10 天。",
            "- 缺少 intrabar protection stop 是 live-executable blocker。",
            "- 首轮不登记版本，不进入 dry-run/live。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{RANKING_CSV.name}`",
            f"- `artifacts/{SLICES_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            f"- `artifacts/{INPUT_4H.name}`",
            f"- `artifacts/{QUALITY_4H.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/sol/4h-rs4-regime-switch/scripts/research_sol_4h_rs4_search.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"selected={selected.spec.name} score={selected.score:.3f} "
        f"prefit_ann={windows['prefit']['annual_multiple']:.4f} "
        f"holdout_ann={windows['reused_holdout']['annual_multiple']:.4f} "
        f"fresh_return={windows['fresh_forward']['total_return']:.4f} "
        f"full_ann={windows['current_full']['annual_multiple']:.4f}",
        flush=True,
    )
    print(f"wrote {REPORT_MD}", flush=True)


if __name__ == "__main__":
    main()
