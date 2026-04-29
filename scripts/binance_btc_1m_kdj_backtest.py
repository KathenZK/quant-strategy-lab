#!/usr/bin/env python3
"""
币安 USDT 永续 BTC 1m K 线，KDJ(9,3,3)：J<20 做多、J>80 做空，中间保持上一状态。
对最近 1 天 / 1 周 / 1 月分别回测总收益与关键指标（含手续费/滑点假设）。

用法（需在项目根目录且已安装依赖）:
  uv run python scripts/binance_btc_1m_kdj_backtest.py
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import ccxt
import numpy as np
import pandas as pd

from strategy_lab.backtest.engine import PortfolioBacktester, _periods_per_year
from strategy_lab.backtest.models import ExecutionAssumptions
from strategy_lab.portfolio import RiskLimits

SYMBOL = "BTC/USDT:USDT"
TIMEFRAME = "1m"
KDJ_N = 9
KDJ_M1 = 3
KDJ_M2 = 3
J_BUY = 20.0
J_SELL = 80.0


@dataclass(frozen=True, slots=True)
class Window:
    name: str
    minutes: int


WINDOWS: tuple[Window, ...] = (
    Window("近 1 天", 24 * 60),
    Window("近 1 周", 7 * 24 * 60),
    Window("近 1 月", 30 * 24 * 60),
)

# 额外多取 K 线，保证窗口起点处 KDJ 已稳定
WARMUP_BARS = 200


def fetch_ohlcv_1m(
    exchange: ccxt.Exchange, *, since_ms: int, end_ms: int, sleep_s: float = 0.05
) -> pd.DataFrame:
    """从 since_ms 到 end_ms 分页拉取 1m OHLCV，返回 UTC 索引 DataFrame。"""
    rows: list[list[float]] = []
    cursor = since_ms
    while cursor < end_ms:
        batch = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, since=cursor, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        last_ts = int(batch[-1][0])
        if last_ts < cursor:
            break
        cursor = last_ts + 1
        if len(batch) < 1000:
            break
        time.sleep(sleep_s)
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df[df["ts"] <= end_ms]
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["ts"], keep="last").sort_values("ts").set_index("ts")
    return df


def kdj_933(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """KDJ(9,3,3): RSV -> K=RSV 的 3 期简单平均, D=K 的 3 期简单平均, J=3K-2D。"""
    low = ohlcv["low"].astype(float)
    high = ohlcv["high"].astype(float)
    close = ohlcv["close"].astype(float)
    ll = low.rolling(KDJ_N, min_periods=KDJ_N).min()
    hh = high.rolling(KDJ_N, min_periods=KDJ_N).max()
    span = (hh - ll).replace(0, np.nan)
    rsv = (close - ll) / span * 100.0
    rsv = rsv.fillna(50.0)
    k = rsv.rolling(KDJ_M1, min_periods=KDJ_M1).mean()
    d = k.rolling(KDJ_M2, min_periods=KDJ_M2).mean()
    j = 3.0 * k - 2.0 * d
    out = ohlcv.copy()
    out["K"], out["D"], out["J"] = k, d, j
    return out


def target_weights_from_j(j: pd.Series) -> pd.Series:
    """J<20 开多(1.0), J>80 开空(-1.0)，其余保持上一非冲突状态。J 为 NaN 时仓位 0。"""
    w = np.zeros(len(j), dtype=np.float64)
    pos = 0.0
    vals = j.to_numpy()
    for i, v in enumerate(vals):
        if np.isnan(v):
            w[i] = 0.0
            continue
        if v < J_BUY:
            pos = 1.0
        elif v > J_SELL:
            pos = -1.0
        w[i] = pos
    s = pd.Series(w, index=j.index, name="weight")
    return s


def _window_backtest(
    ohlcv: pd.DataFrame,
    *,
    end_ts: pd.Timestamp,
    minutes: int,
    backtester: PortfolioBacktester,
) -> dict[str, float] | None:
    """取 [start_ts, end_ts] 区间；多取 1 根前序 K 线，使首根 1m 的成交仓位与全样本一致（shift(1)）。"""
    start_ts = end_ts - pd.Timedelta(minutes=minutes)
    idx = ohlcv.index
    i_first = int(idx.searchsorted(start_ts, side="left"))
    if i_first >= len(ohlcv):
        return None
    i_last = int(idx.searchsorted(end_ts, side="right")) - 1
    if i_last < i_first:
        return None
    i0 = max(0, i_first - 1)
    sub = ohlcv.iloc[i0 : i_last + 1]
    if len(sub) < 2:
        return None

    p = sub[["close"]].rename(columns={"close": SYMBOL})
    tw = sub["weight"].to_frame(SYMBOL)
    result = backtester.run(target_weights=tw, price_frame=p, dollar_volume=None, funding_rate=None)
    eq = result.equity_curve
    pos_start = i_first - i0
    base = float(eq.iloc[pos_start - 1]) if pos_start > 0 else 1.0
    end_eq = float(eq.iloc[-1])
    window_cumret = end_eq / base - 1.0
    pnl = window_cumret * 100_000.0
    # 窗口内（从首根 bar 的期末权益起算）最大回撤
    seg = eq.iloc[pos_start - 1 :].copy()
    if seg.empty:
        return None
    running = seg.cummax()
    dd = (seg / running - 1.0).min()

    pr_w = result.period_returns.iloc[pos_start:]
    ppy = _periods_per_year(pr_w.index)
    mret = float(pr_w.mean()) if not pr_w.empty else 0.0
    v = float(pr_w.std(ddof=0)) if len(pr_w) > 1 else 0.0
    shr = 0.0 if v == 0 else mret / v * (ppy**0.5)
    vol_ann = v * (ppy**0.5)

    return {
        "bars": float(i_last - i_first + 1),
        "cumulative_return": window_cumret,
        "pnl_on_100k": pnl,
        "max_drawdown": float(dd),
        "sharpe": float(shr),
        "volatility": float(vol_ann),
    }


def run() -> None:
    end = datetime.now(timezone.utc)
    end_ms = int(end.timestamp() * 1000)
    max_m = max(w.minutes for w in WINDOWS) + WARMUP_BARS
    since = end - pd.Timedelta(minutes=max_m + 5)
    since_ms = int(since.timestamp() * 1000)

    exchange = ccxt.binance(
        {
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        }
    )

    print("正在从 Binance 拉取 1m K 线（永续，可能需要半分钟）…")
    ohlcv = fetch_ohlcv_1m(exchange, since_ms=since_ms, end_ms=end_ms)
    if ohlcv.empty or len(ohlcv) < WARMUP_BARS:
        print("K 线不足或拉取失败，请检查网络与交易对。")
        return

    ohlcv = kdj_933(ohlcv)
    w_series = target_weights_from_j(ohlcv["J"])
    ohlcv["weight"] = w_series

    assumptions = ExecutionAssumptions(fee_bps=5.0, slippage_bps=2.0, starting_cash=100_000.0)
    risk = RiskLimits(
        max_abs_weight=1.0,
        max_gross_leverage=1.0,
        max_net_exposure=1.0,
        min_dollar_volume=0.0,
    )
    backtester = PortfolioBacktester(assumptions=assumptions, risk_limits=risk)

    end_ts = ohlcv.index.max()
    print(
        f"数据: {ohlcv.index[0].isoformat()} — {end_ts.isoformat()}，"
        f"共 {len(ohlcv)} 根 1m K 线，标的 {SYMBOL}，KDJ({KDJ_N},{KDJ_M1},{KDJ_M2})，J<{J_BUY} 多 / J>{J_SELL} 空，中间持仓不变。\n"
    )

    for w in WINDOWS:
        stats = _window_backtest(ohlcv, end_ts=end_ts, minutes=w.minutes, backtester=backtester)
        if not stats:
            print(f"【{w.name}】样本过短，跳过。")
            continue
        pnl_cash = stats["pnl_on_100k"] * (assumptions.starting_cash / 100_000.0)
        print(
            f"【{w.name}】K 线数(窗口内,约): {int(stats['bars'])} | "
            f"总收益率(区间): {stats['cumulative_return'] * 100:.2f}% | "
            f"等效 PnL（{assumptions.starting_cash:,.0f} 本金）: {pnl_cash:,.2f} U | "
            f"最大回撤(区间内): {stats['max_drawdown'] * 100:.2f}% | "
            f"波动(区间年化约): {stats['volatility'] * 100:.2f}% | "
            f"Sharpe(区间年化约): {stats['sharpe']:.2f}\n"
        )

    print(
        "说明: 回测在当期信号下一根 K 线用收盘价收益率结算（与引擎的 shift(1) 执行一致），"
        "已扣减假设手续费+滑点共 7 bps/单边换手。"
    )


if __name__ == "__main__":
    run()
