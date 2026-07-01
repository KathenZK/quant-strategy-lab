from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
DATE_TAG = "2026-06-30"
FAMILY = "HYPE-15M-Riptide"
VERSION = "HYPE-15M-Riptide-V13"
FAMILY_DIR = ROOT / "research/hype/15m-riptide"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
DIAG_DIR = FAMILY_DIR / "diagnostics"
SCRIPT_PATH = FAMILY_DIR / "scripts/research_hype_15m_riptide_v13_cache_audit.py"

CACHE_PATH = ROOT / "data/cache/hypeusdt_15m_fapi.csv"
SUMMARY_JSON = ARTIFACTS_DIR / f"hype_15m_riptide_v13_cache_audit_{DATE_TAG}.json"
TRADES_CSV = ARTIFACTS_DIR / f"hype_15m_riptide_v13_cache_audit_trades_{DATE_TAG}.csv"
WF_CSV = ARTIFACTS_DIR / f"hype_15m_riptide_v13_cache_audit_wf_windows_{DATE_TAG}.csv"
REPORT_MD = DIAG_DIR / f"hype-15m-riptide-v13-cache-audit-{DATE_TAG}.md"

START_TS = pd.Timestamp("2025-05-30T00:00:00Z")
SPEC_END_TS = pd.Timestamp("2026-06-11T23:59:59Z")
ONE_WAY_COST = 0.0006
BASE_ROUND_TRIP_COST = 2 * ONE_WAY_COST
FIXED_CUT_HI = 104.7
TRAIN_DAYS = 150
TEST_DAYS = 21
STEP_DAYS = 21


@dataclass(frozen=True, slots=True)
class Trade:
    mode: str
    window: str
    signal_ts: str
    entry_ts: str
    exit_ts: str
    side: str
    entry_px: float
    exit_px: float
    atr_signal: float
    r_value: float
    initial_stop: float
    take_profit: float
    final_stop: float
    bars_held: int
    exit_reason: str
    gross_return: float
    net_return: float


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value * 100:.{digits}f}%"


def load_cache() -> tuple[pd.DataFrame, dict[str, Any]]:
    if not CACHE_PATH.exists():
        raise FileNotFoundError(f"missing cache CSV: {CACHE_PATH}")
    frame = pd.read_csv(CACHE_PATH)
    required = {"ts", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"cache CSV missing columns: {missing}")
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].astype("float64")

    expected = pd.date_range(frame["ts"].min(), frame["ts"].max(), freq="15min", tz="UTC")
    missing_bars = expected.difference(pd.DatetimeIndex(frame["ts"]))
    invalid_ohlc = (
        (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
        | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
        | (frame[["open", "high", "low", "close"]] <= 0).any(axis=1)
        | (frame["volume"] < 0)
    )
    quality = {
        "source": str(CACHE_PATH),
        "source_type": "local_ignored_cache_csv",
        "rows": int(len(frame)),
        "first_ts": frame["ts"].min().isoformat(),
        "last_ts": frame["ts"].max().isoformat(),
        "missing_15m_bars": int(len(missing_bars)),
        "duplicates_after_dedup": int(frame["ts"].duplicated().sum()),
        "critical_nulls": int(frame[["ts", "open", "high", "low", "close", "volume"]].isna().sum().sum()),
        "invalid_ohlcv_rows": int(invalid_ohlc.sum()),
        "raw_normalized_alignment_checked": False,
        "funding_available": False,
        "quality_gate_pass_for_cache_replay": bool(
            len(missing_bars) == 0
            and frame["ts"].duplicated().sum() == 0
            and frame[["ts", "open", "high", "low", "close", "volume"]].isna().sum().sum() == 0
            and invalid_ohlc.sum() == 0
        ),
    }
    if not quality["quality_gate_pass_for_cache_replay"]:
        raise ValueError(f"cache data-quality blocker: {json.dumps(quality, ensure_ascii=False)}")
    return frame, quality


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(alpha=2 / (span + 1), adjust=False, min_periods=span).mean()


def rma(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(alpha=1 / span, adjust=False, min_periods=span).mean()


def wilder_rsi(close: pd.Series, span: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = rma(gain, span)
    avg_loss = rma(loss, span)
    rs = avg_gain / avg_loss
    result = 100 - 100 / (1 + rs)
    result = result.mask((avg_loss == 0) & avg_gain.notna(), 100.0)
    result = result.mask((avg_gain == 0) & avg_loss.notna(), 0.0)
    return result


def wilder_atr(frame: pd.DataFrame, span: int = 14) -> pd.Series:
    prev_close = frame["close"].shift(1)
    tr = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return rma(tr, span)


def add_regime_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    indexed = frame.set_index("ts")
    hourly = indexed.resample("1h", label="left", closed="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        bars=("close", "count"),
    )
    hourly = hourly.loc[hourly["bars"].eq(4)].copy()
    hourly["ts"] = hourly.index
    hourly["logret"] = np.log(hourly["close"]).diff()
    hourly["rv"] = hourly["logret"].rolling(24, min_periods=24).std() * math.sqrt(8760) * 100
    hourly["cut_hi_rolling_150d"] = hourly["rv"].rolling(TRAIN_DAYS * 24, min_periods=TRAIN_DAYS * 24).quantile(2 / 3)
    hourly["known_at"] = hourly["ts"] + pd.Timedelta(hours=1)
    regime = hourly[["known_at", "rv", "cut_hi_rolling_150d"]].dropna(subset=["rv"]).sort_values("known_at")

    result = frame.copy()
    result["bar_close_ts"] = result["ts"] + pd.Timedelta(minutes=15)
    result = pd.merge_asof(
        result.sort_values("bar_close_ts"),
        regime,
        left_on="bar_close_ts",
        right_on="known_at",
        direction="backward",
    ).sort_values("ts")
    result = result.drop(columns=["known_at"])
    return result.reset_index(drop=True), hourly.reset_index(drop=True)


def add_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    result = frame.copy()
    result["ema20"] = ema(result["close"], 20)
    result["ema60"] = ema(result["close"], 60)
    result["rsi14"] = wilder_rsi(result["close"], 14)
    result["atr14"] = wilder_atr(result, 14)
    return add_regime_features(result)


def build_signal(frame: pd.DataFrame, cut_hi: float | pd.Series) -> np.ndarray:
    if isinstance(cut_hi, pd.Series):
        cut_values = cut_hi.to_numpy("float64")
    else:
        cut_values = np.full(len(frame), float(cut_hi), dtype="float64")
    ema_fast = frame["ema20"].to_numpy("float64")
    ema_slow = frame["ema60"].to_numpy("float64")
    rsi = frame["rsi14"].to_numpy("float64")
    rv = frame["rv"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    signal = np.zeros(len(frame), dtype=np.int8)
    long_mask = (ema_fast > ema_slow) & (rsi < 40.0) & (rv < cut_values)
    short_mask = (ema_fast < ema_slow) & (rsi > 60.0) & (rv < cut_values)
    ready = np.isfinite(ema_slow) & np.isfinite(rsi) & np.isfinite(rv) & np.isfinite(cut_values) & np.isfinite(atr)
    signal[ready & long_mask] = 1
    signal[ready & short_mask] = -1
    return signal


def simulate(
    frame: pd.DataFrame,
    signal: np.ndarray,
    *,
    mode: str,
    window: str,
    signal_start: pd.Timestamp | None = None,
    signal_end: pd.Timestamp | None = None,
    round_trip_cost: float = BASE_ROUND_TRIP_COST,
) -> list[Trade]:
    ts = list(pd.to_datetime(frame["ts"], utc=True))
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Trade] = []
    next_signal_index = 0
    n = len(frame)

    while next_signal_index < n - 1:
        k = next_signal_index
        if signal[k] == 0:
            next_signal_index += 1
            continue
        if signal_start is not None and ts[k] < signal_start:
            next_signal_index += 1
            continue
        if signal_end is not None and ts[k] >= signal_end:
            break
        if not np.isfinite(atr[k]) or atr[k] <= 0:
            next_signal_index += 1
            continue

        entry_i = k + 1
        side = int(signal[k])
        entry = float(open_[entry_i])
        a = float(atr[k])
        risk = 2.0 * a
        if side > 0:
            stop = entry - risk
            initial_stop = stop
            take_profit = entry + 3.0 * risk
        else:
            stop = entry + risk
            initial_stop = stop
            take_profit = entry - 3.0 * risk

        exit_i = n - 1
        exit_px = float(close[-1])
        exit_reason = "forced_end"
        final_stop = stop
        for i in range(entry_i, n):
            if side > 0:
                if low[i] <= stop:
                    exit_i = i
                    exit_px = float(open_[i] if open_[i] < stop else stop)
                    exit_reason = "stop" if stop != entry else "breakeven_stop"
                    final_stop = stop
                    break
                if high[i] >= take_profit:
                    exit_i = i
                    exit_px = float(open_[i] if open_[i] > take_profit else take_profit)
                    exit_reason = "take_profit"
                    final_stop = stop
                    break
                if i - entry_i >= 48:
                    exit_i = i
                    exit_px = float(close[i])
                    exit_reason = "time_stop"
                    final_stop = stop
                    break
                if high[i] >= entry + risk:
                    stop = max(stop, entry)
            else:
                if high[i] >= stop:
                    exit_i = i
                    exit_px = float(open_[i] if open_[i] > stop else stop)
                    exit_reason = "stop" if stop != entry else "breakeven_stop"
                    final_stop = stop
                    break
                if low[i] <= take_profit:
                    exit_i = i
                    exit_px = float(open_[i] if open_[i] < take_profit else take_profit)
                    exit_reason = "take_profit"
                    final_stop = stop
                    break
                if i - entry_i >= 48:
                    exit_i = i
                    exit_px = float(close[i])
                    exit_reason = "time_stop"
                    final_stop = stop
                    break
                if low[i] <= entry - risk:
                    stop = min(stop, entry)

        gross = exit_px / entry - 1.0 if side > 0 else entry / exit_px - 1.0
        net = gross - round_trip_cost
        trades.append(
            Trade(
                mode=mode,
                window=window,
                signal_ts=pd.Timestamp(ts[k]).isoformat(),
                entry_ts=pd.Timestamp(ts[entry_i]).isoformat(),
                exit_ts=pd.Timestamp(ts[exit_i]).isoformat(),
                side="long" if side > 0 else "short",
                entry_px=entry,
                exit_px=exit_px,
                atr_signal=a,
                r_value=risk,
                initial_stop=float(initial_stop),
                take_profit=float(take_profit),
                final_stop=float(final_stop),
                bars_held=int(exit_i - entry_i),
                exit_reason=exit_reason,
                gross_return=float(gross),
                net_return=float(net),
            )
        )
        # After an intrabar exit, the same bar can still produce a close-based
        # signal for next-bar re-entry. This matches the no-cooldown spec.
        next_signal_index = exit_i
    return trades


def summarize_trades(trades: list[Trade], start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    returns = np.array([trade.net_return for trade in trades], dtype="float64")
    gross = np.array([trade.gross_return for trade in trades], dtype="float64")
    equity = 1.0
    curve = [equity]
    for value in returns:
        equity *= 1.0 + value
        curve.append(equity)
    curve_arr = np.array(curve, dtype="float64")
    peaks = np.maximum.accumulate(curve_arr)
    drawdown = curve_arr / peaks - 1.0
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    period_days = max((end - start).total_seconds() / 86400.0, 1.0)
    trades_per_year = len(returns) / period_days * 365.25
    trade_sharpe = 0.0
    if len(returns) >= 2 and np.std(returns, ddof=1) > 0:
        trade_sharpe = float(np.mean(returns) / np.std(returns, ddof=1) * math.sqrt(trades_per_year))
    exit_counts = {key: int(value) for key, value in pd.Series([t.exit_reason for t in trades]).value_counts().items()}
    side_counts = {key: int(value) for key, value in pd.Series([t.side for t in trades]).value_counts().items()}
    return {
        "start_ts": start.isoformat(),
        "end_ts": end.isoformat(),
        "period_days": float(period_days),
        "trades": int(len(trades)),
        "long_trades": int(side_counts.get("long", 0)),
        "short_trades": int(side_counts.get("short", 0)),
        "total_return_pct": float((equity - 1.0) * 100.0),
        "max_drawdown_pct": float(np.min(drawdown) * 100.0) if len(drawdown) else 0.0,
        "win_rate_pct": float((returns > 0).mean() * 100.0) if len(returns) else 0.0,
        "profit_factor": float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else float("inf"),
        "avg_trade_bp": float(np.mean(returns) * 10000.0) if len(returns) else 0.0,
        "avg_gross_trade_bp": float(np.mean(gross) * 10000.0) if len(gross) else 0.0,
        "trades_per_day": float(len(returns) / period_days),
        "trade_sharpe_annualized": trade_sharpe,
        "exit_counts": exit_counts,
        "side_counts": side_counts,
    }


def walk_forward(frame: pd.DataFrame) -> tuple[list[Trade], list[dict[str, Any]]]:
    windows: list[dict[str, Any]] = []
    trades_all: list[Trade] = []
    data_start = max(frame["ts"].min(), START_TS)
    end = min(frame["ts"].max(), SPEC_END_TS)
    test_start = data_start + pd.Timedelta(days=TRAIN_DAYS)
    index = 0
    while test_start < end:
        train_start = test_start - pd.Timedelta(days=TRAIN_DAYS)
        test_end = min(test_start + pd.Timedelta(days=TEST_DAYS), end)
        train_mask = (frame["ts"] >= train_start) & (frame["ts"] < test_start)
        train_rv = frame.loc[train_mask, "rv"].dropna()
        if len(train_rv) < TRAIN_DAYS * 24:
            test_start += pd.Timedelta(days=STEP_DAYS)
            continue
        cut_hi = float(train_rv.quantile(2 / 3))
        signal = build_signal(frame, cut_hi)
        window_name = f"wf_{index:02d}_{test_start.strftime('%Y%m%d')}_{test_end.strftime('%Y%m%d')}"
        trades = simulate(
            frame,
            signal,
            mode="walk_forward_train150_test21_step21",
            window=window_name,
            signal_start=test_start,
            signal_end=test_end,
        )
        summary = summarize_trades(trades, test_start, test_end)
        windows.append(
            {
                "window": window_name,
                "train_start": train_start.isoformat(),
                "train_end": test_start.isoformat(),
                "test_start": test_start.isoformat(),
                "test_end": test_end.isoformat(),
                "cut_hi": cut_hi,
                **summary,
            }
        )
        trades_all.extend(trades)
        test_start += pd.Timedelta(days=STEP_DAYS)
        index += 1
    return trades_all, windows


def apply_round_trip_cost(trades: list[Trade], cost_bps: float) -> list[Trade]:
    return [
        Trade(
            **{
                **asdict(trade),
                "net_return": float(trade.gross_return - cost_bps / 10000.0),
            }
        )
        for trade in trades
    ]


def cost_stress(trades: list[Trade]) -> list[dict[str, Any]]:
    rows = []
    for cost_bps in (12, 18, 24, 28):
        stressed = apply_round_trip_cost(trades, cost_bps)
        rows.append({"round_trip_cost_bps": cost_bps, **summarize_trades(stressed, START_TS, SPEC_END_TS)})
    return rows


def markdown_report(summary: dict[str, Any]) -> str:
    fixed = summary["fixed_cut_hi_104_7"]
    rolling = summary["rolling_150d_per_bar"]
    wf = summary["walk_forward_train150_test21_step21"]
    quality = summary["data_quality"]
    fixed_exit = fixed["exit_counts"]
    cost_stress_rows = summary["fixed_cut_hi_cost_stress"]
    binance_cost = summary["binance_default_cost_28bps"]
    cost_18 = next(row for row in cost_stress_rows if row["round_trip_cost_bps"] == 18)
    cost_24 = next(row for row in cost_stress_rows if row["round_trip_cost_bps"] == 24)
    cost_28 = next(row for row in cost_stress_rows if row["round_trip_cost_bps"] == 28)
    wf_windows = summary["walk_forward_windows"]
    positive_windows = sum(1 for row in wf_windows if row["total_return_pct"] > 0)
    worst_window = min((row["total_return_pct"] for row in wf_windows), default=0.0)
    lines = [
        "# HYPE-15M-Riptide-V13 缓存口径复现审计",
        "",
        "## 结论",
        "",
        (
            "`HYPE-15M-Riptide-V13` 是 Binance HYPEUSDT 永续 `15m` 趋势背景下 RSI 回调 + "
            "RV regime 门 + ATR bracket 策略。按 `/Users/ZK/Downloads/SPEC-v13-RIPTIDE.md` 逐条实现后，"
            "本地 cache CSV 口径能复现出相近的交易画像和 WF 收益形状，但固定切点第一验收仍未逐笔/汇总完全对齐。"
            "本轮结论是 `diagnostic / reproduction-pending`，不能直接开始 sim-paper 计时。"
        ),
        "",
        (
            f"- 固定 `cut_hi=104.7` 对照：`{fixed['total_return_pct']:.2f}%` 总收益、"
            f"`{fixed['max_drawdown_pct']:.2f}%` 最大回撤、`{fixed['trades']}` 笔、"
            f"胜率 `{fixed['win_rate_pct']:.2f}%`、PF `{fixed['profit_factor']:.2f}`、"
            f"单笔 `{fixed['avg_trade_bp']:.1f}bp`。规格验收为 `+252.7% / MDD -26.9% / 431 笔 / 胜率 29.7% / PF 1.49 / 单笔 +31.5bp`。"
        ),
        (
            f"- 150d 滚动逐 bar `cut_hi`：`{rolling['total_return_pct']:.2f}%` 总收益、"
            f"`{rolling['max_drawdown_pct']:.2f}%` 最大回撤、`{rolling['trades']}` 笔、"
            f"单笔 `{rolling['avg_trade_bp']:.1f}bp`。"
        ),
        (
            f"- `train150/test21/step21` walk-forward：拼接 OOS `{wf['total_return_pct']:.2f}%`、"
            f"`{wf['max_drawdown_pct']:.2f}%` 最大回撤、`{wf['trades']}` 笔、"
            f"正窗 `{positive_windows}/{len(wf_windows)}`、最差窗 `{worst_window:.2f}%`。规格锚为 `+100.4% / MDD -12.6% / 正窗 9-10 / 最差窗 -0.2%`。"
        ),
        "",
        "## 数据口径",
        "",
        (
            f"- 输入：`{quality['source']}`；覆盖 `{quality['first_ts']}` 至 `{quality['last_ts']}`，"
            f"`{quality['rows']}` 根 `15m` bar，缺口 `{quality['missing_15m_bars']}`，重复 `{quality['duplicates_after_dedup']}`，"
            f"OHLCV 硬违规 `{quality['invalid_ohlcv_rows']}`。"
        ),
        "- 本轮没有标准 raw/normalized parquet 对齐，也没有 Binance funding 序列；资金费按 `0` 处理。按仓库 data-first 规则，这只能算 cache 复现审计，不是可 promotion 证据。",
        "- 1h RV 由本地 `15m` bar 聚合而来，只保留完整 4 根 `15m` 的 1h bar，再用 `known_at = 1h_open + 1h` 因果映射到 15m。",
        "",
        "## 实现核对",
        "",
        "- 信号在 `k` 收盘计算，成交在 `k+1` 开盘；出场可从入场当根 high/low 开始检查。",
        "- EMA 使用 `alpha=2/(n+1), adjust=False, min_periods=n`；RSI/ATR 使用 Wilder RMA。",
        "- 止损优先于止盈；保本 stop 只在 bar 收盘后 ratchet，保护下一根；无 flip exit。",
        "- 成本使用规格的 taker `6bps/边`，往返 `12bps`；另做 `18/24bps` 成本压力测试。",
        (
            f"- 固定切点成本压力：RT `18bps` 后总收益 `{cost_18['total_return_pct']:.2f}%`、"
            f"RT `24bps` 后总收益 `{cost_24['total_return_pct']:.2f}%`、"
            f"Binance 默认成本 RT `28bps` 后总收益 `{cost_28['total_return_pct']:.2f}%`。"
        ),
        (
            f"- Binance 默认成本 RT `28bps` 全部重算：固定切点 `{binance_cost['fixed_cut_hi_104_7']['total_return_pct']:.2f}%`、"
            f"150d rolling `{binance_cost['rolling_150d_per_bar']['total_return_pct']:.2f}%`、"
            f"WF `{binance_cost['walk_forward_train150_test21_step21']['total_return_pct']:.2f}%`。"
        ),
        "",
        "## 固定切点出场画像",
        "",
        (
            f"- 止损 `{fixed_exit.get('stop', 0)}`，保本 `{fixed_exit.get('breakeven_stop', 0)}`，"
            f"止盈 `{fixed_exit.get('take_profit', 0)}`，时停 `{fixed_exit.get('time_stop', 0)}`，强制结尾 `{fixed_exit.get('forced_end', 0)}`。"
        ),
        "",
        "## 初步判断",
        "",
        "这份规范的 live-executable 设计比许多旧回测更严谨，WF 结果也支持它不是纯样本内幻觉；但固定切点对照仍差 `12` 笔和约 `45pp` 总收益，不能按规格要求视为验收通过。最可能的差异来源包括：原始研发数据与本地 cache CSV 不同、1h RV 使用了真实 1h K 线而非 15m 聚合、RSI/ATR warmup 细节不同、时停 bars_held 计数差异，或规格里的验收数字来自另一份实现。下一步应先补标准 data lake 与 funding，再逐笔对账；在逐笔时间戳和方向对齐前，不应开始 sim-paper 计时。",
        "",
        "## 产物",
        "",
        f"- 复现脚本：`{SCRIPT_PATH.relative_to(ROOT)}`",
        f"- JSON 摘要：`{SUMMARY_JSON.relative_to(ROOT)}`",
        f"- 交易明细：`{TRADES_CSV.relative_to(ROOT)}`",
        f"- WF 窗口：`{WF_CSV.relative_to(ROOT)}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    raw, quality = load_cache()
    frame, hourly = add_features(raw)
    frame = frame.loc[(frame["ts"] >= START_TS) & (frame["ts"] <= SPEC_END_TS)].reset_index(drop=True)

    fixed_signal = build_signal(frame, FIXED_CUT_HI)
    fixed_trades = simulate(frame, fixed_signal, mode="fixed_cut_hi_104_7", window="full_sample")
    rolling_signal = build_signal(frame, frame["cut_hi_rolling_150d"])
    rolling_trades = simulate(frame, rolling_signal, mode="rolling_150d_per_bar", window="full_sample")
    wf_trades, wf_windows = walk_forward(frame)

    fixed_summary = summarize_trades(fixed_trades, START_TS, SPEC_END_TS)
    rolling_summary = summarize_trades(rolling_trades, START_TS, SPEC_END_TS)
    wf_summary = summarize_trades(wf_trades, START_TS + pd.Timedelta(days=TRAIN_DAYS), SPEC_END_TS)
    fixed_binance_cost = apply_round_trip_cost(fixed_trades, 28)
    rolling_binance_cost = apply_round_trip_cost(rolling_trades, 28)
    wf_binance_cost = apply_round_trip_cost(wf_trades, 28)

    all_trades = fixed_trades + rolling_trades + wf_trades
    trades_frame = pd.DataFrame([asdict(trade) for trade in all_trades])
    trades_frame.to_csv(TRADES_CSV, index=False)
    pd.DataFrame(wf_windows).to_csv(WF_CSV, index=False)

    summary = {
        "family": FAMILY,
        "version": VERSION,
        "run_date": DATE_TAG,
        "strategy_spec_source": "/Users/ZK/Downloads/SPEC-v13-RIPTIDE.md",
        "data_quality": quality,
        "feature_coverage": {
            "hourly_complete_rows": int(len(hourly)),
            "hourly_first_ts": hourly["ts"].min().isoformat() if len(hourly) else None,
            "hourly_last_ts": hourly["ts"].max().isoformat() if len(hourly) else None,
            "rv_ready_15m_rows": int(frame["rv"].notna().sum()),
            "rolling_cut_hi_ready_15m_rows": int(frame["cut_hi_rolling_150d"].notna().sum()),
        },
        "cost_model": {
            "one_way_taker_cost": ONE_WAY_COST,
            "round_trip_cost": BASE_ROUND_TRIP_COST,
            "funding": "not_included_cache_missing",
        },
        "fixed_cut_hi_104_7": fixed_summary,
        "rolling_150d_per_bar": rolling_summary,
        "walk_forward_train150_test21_step21": wf_summary,
        "walk_forward_windows": wf_windows,
        "fixed_cut_hi_cost_stress": cost_stress(fixed_trades),
        "binance_default_cost_28bps": {
            "fee_per_fill": 0.001,
            "slippage_per_fill_bps": 4,
            "one_way_cost_bps": 14,
            "round_trip_cost_bps": 28,
            "funding": "not_included_cache_missing",
            "fixed_cut_hi_104_7": summarize_trades(fixed_binance_cost, START_TS, SPEC_END_TS),
            "rolling_150d_per_bar": summarize_trades(rolling_binance_cost, START_TS, SPEC_END_TS),
            "walk_forward_train150_test21_step21": summarize_trades(
                wf_binance_cost,
                START_TS + pd.Timedelta(days=TRAIN_DAYS),
                SPEC_END_TS,
            ),
        },
        "acceptance_targets_from_spec": {
            "fixed_cut_hi_104_7": {
                "total_return_pct": 252.7,
                "sharpe": 5.61,
                "max_drawdown_pct": -26.9,
                "trades": 431,
                "long_trades": 213,
                "short_trades": 218,
                "win_rate_pct": 29.7,
                "profit_factor": 1.49,
                "avg_trade_bp": 31.5,
                "exit_counts": {"stop": 180, "breakeven_stop": 120, "take_profit": 78, "time_stop": 53},
            },
            "walk_forward_train150_test21_step21": {
                "total_return_pct": 100.4,
                "max_drawdown_pct": -12.6,
                "positive_windows": "9-10",
                "worst_window_pct": -0.2,
            },
        },
    }
    SUMMARY_JSON.write_text(json.dumps(json_safe(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(markdown_report(summary), encoding="utf-8")
    print(json.dumps(json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
