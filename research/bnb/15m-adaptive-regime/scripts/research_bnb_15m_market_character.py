from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/bnb/15m-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
DATA_PATH = ARTIFACT_DIR / "bnb_binance_15m_closed_klines_2y.parquet"
DATE_TAG = "2026-07-05"
OUTPUT_JSON = ARTIFACT_DIR / f"bnb_15m_market_character_{DATE_TAG}.json"
EVENT_CSV = ARTIFACT_DIR / f"bnb_15m_market_character_events_{DATE_TAG}.csv"
SESSION_CSV = ARTIFACT_DIR / f"bnb_15m_market_character_sessions_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"bnb-15m-market-character-{DATE_TAG}.md"

ROUND_TRIP_COST = 2 * (0.001 + 0.0004)
OOS_MONTHS = 3


def rsi(series: pd.Series, window: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - 100.0 / (1.0 + rs)


def adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    previous_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index)
    atr = tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    plus = 100 * plus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr.replace(0.0, np.nan)
    minus = 100 * minus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr.replace(0.0, np.nan)
    dx = 100 * (plus - minus).abs() / (plus + minus).replace(0.0, np.nan)
    return dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"].astype(float)
    high = result["high"].astype(float)
    low = result["low"].astype(float)
    open_ = result["open"].astype(float)
    volume = result["volume"].astype(float)
    previous_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    result["atr14"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    result["atr_bps"] = result["atr14"] / close * 10_000
    for span in (12, 20, 48, 80, 192, 384):
        result[f"ema{span}"] = close.ewm(span=span, adjust=False, min_periods=span).mean()
    for window in (4, 12, 24, 48, 96):
        result[f"ret{window}_bps"] = close.pct_change(window) * 10_000
    result["rsi7"] = rsi(close, 7)
    result["rsi14"] = rsi(close, 14)
    result["adx14"] = adx(high, low, close)
    result["rvol96"] = volume / volume.rolling(96, min_periods=96).mean()
    result["body_atr"] = (close - open_) / result["atr14"].replace(0.0, np.nan)
    result["close_pos"] = (close - low) / (high - low).replace(0.0, np.nan)
    mid = close.rolling(48, min_periods=48).mean()
    std = close.rolling(48, min_periods=48).std(ddof=0)
    width = 4 * std / mid
    result["bb_z48"] = (close - mid) / std.replace(0.0, np.nan)
    result["bb_width_pct"] = width.rolling(672, min_periods=672).rank(pct=True)
    for window in (24, 48, 96, 192):
        result[f"don_high{window}"] = high.shift(1).rolling(window, min_periods=window).max()
        result[f"don_low{window}"] = low.shift(1).rolling(window, min_periods=window).min()
    return result


def summarize_event(
    frame: pd.DataFrame,
    signal: np.ndarray,
    name: str,
    horizon: int,
) -> dict[str, Any]:
    entry = frame["open"].shift(-1).to_numpy(float)
    exit_ = frame["open"].shift(-(horizon + 1)).to_numpy(float)
    valid = (signal != 0) & np.isfinite(entry) & np.isfinite(exit_)
    returns = signal[valid] * (exit_[valid] / entry[valid] - 1.0) - ROUND_TRIP_COST
    count = int(len(returns))
    positive = returns[returns > 0]
    negative = -returns[returns < 0]
    return {
        "event": name,
        "horizon_bars": horizon,
        "count": count,
        "long_count": int(np.sum(signal[valid] > 0)),
        "short_count": int(np.sum(signal[valid] < 0)),
        "mean_net_return": float(np.mean(returns)) if count else 0.0,
        "median_net_return": float(np.median(returns)) if count else 0.0,
        "win_rate": float(np.mean(returns > 0)) if count else 0.0,
        "profit_factor": float(positive.sum() / negative.sum()) if negative.sum() else math.inf,
        "t_stat": float(np.mean(returns) / (np.std(returns, ddof=1) / np.sqrt(count)))
        if count > 2 and np.std(returns, ddof=1) > 0
        else 0.0,
    }


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError("Run fetch_bnb_binance_15m.py first")
    frame = pd.read_parquet(DATA_PATH)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    full_end = frame["ts"].iloc[-1] + pd.Timedelta(minutes=15)
    oos_start = full_end - pd.DateOffset(months=OOS_MONTHS)
    prefit = frame.loc[frame["ts"] < oos_start].copy().reset_index(drop=True)
    featured = add_features(prefit)
    close = featured["close"].to_numpy(float)
    open_ = featured["open"].to_numpy(float)
    high = featured["high"].to_numpy(float)
    low = featured["low"].to_numpy(float)
    atr = featured["atr14"].to_numpy(float)
    rvol = featured["rvol96"].to_numpy(float)
    adx_values = featured["adx14"].to_numpy(float)
    ema20 = featured["ema20"].to_numpy(float)
    ema80 = featured["ema80"].to_numpy(float)
    ema192 = featured["ema192"].to_numpy(float)
    ret4 = featured["ret4_bps"].to_numpy(float)
    ret12 = featured["ret12_bps"].to_numpy(float)
    body = featured["body_atr"].to_numpy(float)
    width_pct = featured["bb_width_pct"].to_numpy(float)
    close_pos = featured["close_pos"].to_numpy(float)

    def cross_up(a: np.ndarray, b: np.ndarray | float) -> np.ndarray:
        b_values = np.full_like(a, b) if np.isscalar(b) else b
        return (a > b_values) & (np.r_[np.nan, a[:-1]] <= np.r_[np.nan, b_values[:-1]])

    def cross_down(a: np.ndarray, b: np.ndarray | float) -> np.ndarray:
        b_values = np.full_like(a, b) if np.isscalar(b) else b
        return (a < b_values) & (np.r_[np.nan, a[:-1]] >= np.r_[np.nan, b_values[:-1]])

    events: dict[str, np.ndarray] = {}
    for window in (24, 48, 96, 192):
        upper = featured[f"don_high{window}"].to_numpy(float)
        lower = featured[f"don_low{window}"].to_numpy(float)
        signal = np.zeros(len(featured), dtype=np.int8)
        signal[cross_up(close, upper)] = 1
        signal[cross_down(close, lower)] = -1
        events[f"donchian_{window}"] = signal

    signal = np.zeros(len(featured), dtype=np.int8)
    signal[(ema20 > ema80) & (ema80 > ema192) & (low <= ema20 + 0.25 * atr) & (close > ema20) & (close_pos >= 0.65)] = 1
    signal[(ema20 < ema80) & (ema80 < ema192) & (high >= ema20 - 0.25 * atr) & (close < ema20) & (close_pos <= 0.35)] = -1
    signal[np.r_[False, signal[1:] == signal[:-1]] & (signal != 0)] = 0
    events["trend_pullback_recovery"] = signal

    signal = np.zeros(len(featured), dtype=np.int8)
    signal[(ret12 <= -250) & (ret4 > 0) & (close > open_) & (close_pos >= 0.7)] = 1
    signal[(ret12 >= 250) & (ret4 < 0) & (close < open_) & (close_pos <= 0.3)] = -1
    events["shock_structure_repair"] = signal

    signal = np.zeros(len(featured), dtype=np.int8)
    signal[(rvol >= 1.5) & (body >= 0.75) & (adx_values >= 20) & (ema20 > ema80)] = 1
    signal[(rvol >= 1.5) & (body <= -0.75) & (adx_values >= 20) & (ema20 < ema80)] = -1
    signal[np.r_[False, signal[1:] == signal[:-1]] & (signal != 0)] = 0
    events["volume_trend_impulse"] = signal

    signal = np.zeros(len(featured), dtype=np.int8)
    zscore = featured["bb_z48"].to_numpy(float)
    previous_squeeze = np.r_[False, width_pct[:-1] <= 0.2]
    signal[previous_squeeze & cross_up(zscore, 1.0) & (rvol >= 1.0)] = 1
    signal[previous_squeeze & cross_down(zscore, -1.0) & (rvol >= 1.0)] = -1
    events["squeeze_release"] = signal

    signal = np.zeros(len(featured), dtype=np.int8)
    signal[cross_up(ret12, 150.0) & (rvol >= 1.0) & (ema20 > ema80)] = 1
    signal[cross_down(ret12, -150.0) & (rvol >= 1.0) & (ema20 < ema80)] = -1
    events["regime_momentum_12"] = signal

    rows = [
        summarize_event(featured, signal, name, horizon)
        for name, signal in events.items()
        for horizon in (4, 8, 16, 32, 64)
    ]
    rows.sort(key=lambda row: (row["mean_net_return"], row["t_stat"]), reverse=True)
    pd.DataFrame(rows).to_csv(EVENT_CSV, index=False)

    next_4 = featured["open"].shift(-5) / featured["open"].shift(-1) - 1.0
    session_rows: list[dict[str, Any]] = []
    for hour, group in featured.assign(next_4=next_4).dropna(subset=["next_4"]).groupby(featured["ts"].dt.hour):
        values = group["next_4"].to_numpy(float)
        session_rows.append(
            {
                "utc_hour": int(hour),
                "count": int(len(values)),
                "mean_raw_4bar_return": float(np.mean(values)),
                "up_rate": float(np.mean(values > 0)),
                "mean_abs_4bar_return": float(np.mean(np.abs(values))),
            }
        )
    pd.DataFrame(session_rows).to_csv(SESSION_CSV, index=False)

    returns = featured["close"].pct_change().dropna()
    autocorrelation = {
        str(lag): float(returns.autocorr(lag)) for lag in (1, 2, 4, 8, 16, 32, 96)
    }
    volatility = {
        "atr_bps_p10": float(np.nanpercentile(featured["atr_bps"], 10)),
        "atr_bps_p25": float(np.nanpercentile(featured["atr_bps"], 25)),
        "atr_bps_p50": float(np.nanpercentile(featured["atr_bps"], 50)),
        "atr_bps_p75": float(np.nanpercentile(featured["atr_bps"], 75)),
        "atr_bps_p90": float(np.nanpercentile(featured["atr_bps"], 90)),
        "round_trip_cost_bps": ROUND_TRIP_COST * 10_000,
    }
    payload = {
        "family": "BNB-15M-Adaptive-Regime",
        "prefit_only": True,
        "raw_start": frame["ts"].iloc[0],
        "prefit_end": oos_start,
        "locked_oos_start": oos_start,
        "full_end": full_end,
        "prefit_rows": int(len(prefit)),
        "autocorrelation": autocorrelation,
        "volatility": volatility,
        "top_events": rows[:30],
        "session_rows": session_rows,
    }
    OUTPUT_JSON.write_text(
        json.dumps(payload, default=str, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# BNB 15m 行情结构诊断 - 2026-07-05",
        "",
        "## 边界",
        "",
        f"- 只使用 `{frame['ts'].iloc[0].isoformat()}` 至 `{oos_start.isoformat()}` 的 prefit 数据。",
        f"- `{oos_start.isoformat()}` 至 `{full_end.isoformat()}` 保持 locked，本文没有读取其收益结构。",
        f"- Binance round-trip 默认成本为 `{ROUND_TRIP_COST * 100:.2f}%`（`{ROUND_TRIP_COST * 10_000:.1f} bps`）。",
        "",
        "## 波动与自相关",
        "",
        f"- ATR14 bps P10/P25/P50/P75/P90：`{volatility['atr_bps_p10']:.1f}` / `{volatility['atr_bps_p25']:.1f}` / `{volatility['atr_bps_p50']:.1f}` / `{volatility['atr_bps_p75']:.1f}` / `{volatility['atr_bps_p90']:.1f}`。",
        "- close-to-close return autocorr：" + ", ".join(f"lag {key}=`{value:.4f}`" for key, value in autocorrelation.items()) + "。",
        "",
        "## 扣除成本后的事件前沿",
        "",
        "| Event | Hold | Count | Mean net | Win | PF | t-stat |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows[:20]:
        lines.append(
            f"| `{row['event']}` | `{row['horizon_bars']}` | `{row['count']}` | `{row['mean_net_return']:.3%}` | `{row['win_rate']:.2%}` | `{row['profit_factor']:.3f}` | `{row['t_stat']:.2f}` |"
        )
    lines.extend(
        [
            "",
            "## 对搜索的约束",
            "",
            "- 15m 的默认 round-trip 成本相对单根 ATR 不可忽略，搜索必须压低无效换手，优先 4–16 小时持仓而非超短 scalping。",
            "- 事件表只用于确定机制与参数尺度；最终排序仍必须经过 train/validation、逐笔保护单模拟和唯一 primary locked OOS。",
            "- 不把单一时段均值直接做成策略；UTC hour 只允许作为机械消融项，防止 session 过拟合。",
            "",
        ]
    )
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"volatility": volatility, "autocorrelation": autocorrelation, "top_events": rows[:10]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
