from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = (
    PROJECT_ROOT
    / "data"
    / "normalized"
    / "ohlcv"
    / "exchange=binance"
    / "market_type=perp"
    / "timeframe=15m"
)
REPORT_PREFIX = PROJECT_ROOT / "reports" / "minara_rsi2065_btc_hype"
BARS_PER_YEAR = 365 * 24 * 4


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    timeframe: str = "15m"
    rsi_window: int = 14
    rsi_long_threshold: float = 20.0
    rsi_short_threshold: float = 65.0
    stochastic_window: int = 14
    stochastic_long_threshold: float = 25.0
    stochastic_short_threshold: float = 75.0
    ema_window: int = 200
    stop_loss_pct: float = 0.04
    take_profit_pct: float = 0.06
    allocation: float = 1.0
    fee_rate: float = 0.00045
    entry_price: str = "signal_bar_close"
    exit_price: str = "intrabar_high_low_stop_first"


def _symbol_stem(symbol: str) -> str:
    return symbol.replace("/", "_").replace(":", "_").lower()


def load_ohlcv(symbol: str) -> pd.DataFrame:
    files = sorted(DATA_ROOT.glob(f"date=*/symbol={_symbol_stem(symbol)}.parquet"))
    if not files:
        raise FileNotFoundError(f"no 15m parquet files found for {symbol}")
    query = """
        SELECT ts, open, high, low, close, volume, quote_volume, is_closed
        FROM read_parquet(?, hive_partitioning = false, union_by_name = true)
        ORDER BY ts
    """
    with duckdb.connect() as connection:
        frame = connection.execute(query, [[str(path) for path in files]]).fetch_df()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.drop_duplicates(subset=["ts"], keep="last").sort_values("ts")
    frame = frame[frame["is_closed"].fillna(True).astype(bool)].copy()
    frame = frame.set_index("ts")
    for column in ("open", "high", "low", "close", "volume", "quote_volume"):
        if column in frame:
            frame[column] = frame[column].astype("float64")
    return frame


def rsi_wilder(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    relative_strength = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + relative_strength)
    rsi = rsi.mask((avg_loss == 0.0) & (avg_gain > 0.0), 100.0)
    rsi = rsi.mask((avg_gain == 0.0) & (avg_loss > 0.0), 0.0)
    rsi = rsi.mask((avg_gain == 0.0) & (avg_loss == 0.0), 50.0)
    return rsi


def add_indicators(frame: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    enriched = frame.copy()
    close = enriched["close"]
    low_min = enriched["low"].rolling(
        config.stochastic_window, min_periods=config.stochastic_window
    ).min()
    high_max = enriched["high"].rolling(
        config.stochastic_window, min_periods=config.stochastic_window
    ).max()
    denominator = (high_max - low_min).replace(0.0, np.nan)
    enriched["rsi"] = rsi_wilder(close, config.rsi_window)
    enriched["stoch_k"] = 100.0 * (close - low_min) / denominator
    enriched["ema_200"] = close.ewm(
        span=config.ema_window, adjust=False, min_periods=config.ema_window
    ).mean()
    return enriched


def max_drawdown(equity: pd.Series) -> float:
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min()) if not drawdown.empty else 0.0


def summarize(
    *,
    symbol: str,
    window_name: str,
    frame: pd.DataFrame,
    equity_curve: pd.Series,
    trades: pd.DataFrame,
    config: StrategyConfig,
) -> dict[str, float | int | str | None]:
    years = (
        (equity_curve.index[-1] - equity_curve.index[0]).total_seconds()
        / (365.0 * 24.0 * 60.0 * 60.0)
        if len(equity_curve) > 1
        else 0.0
    )
    cumulative_return = float(equity_curve.iloc[-1] - 1.0) if len(equity_curve) else 0.0
    annualized_return = (
        float(equity_curve.iloc[-1] ** (1.0 / years) - 1.0)
        if years > 0 and len(equity_curve)
        else 0.0
    )
    period_returns = equity_curve.pct_change().fillna(0.0)
    volatility = float(period_returns.std(ddof=0) * np.sqrt(BARS_PER_YEAR))
    sharpe = (
        float(period_returns.mean() / period_returns.std(ddof=0) * np.sqrt(BARS_PER_YEAR))
        if period_returns.std(ddof=0) > 0
        else 0.0
    )
    net_returns = trades["net_return"] if not trades.empty else pd.Series(dtype=float)
    wins = int(net_returns.gt(0.0).sum())
    losses = int(net_returns.le(0.0).sum())
    gross_profit = float(net_returns[net_returns > 0.0].sum()) if wins else 0.0
    gross_loss = float(-net_returns[net_returns < 0.0].sum()) if losses else 0.0
    return {
        "symbol": symbol,
        "window": window_name,
        "start": equity_curve.index[0].isoformat() if len(equity_curve) else None,
        "end": equity_curve.index[-1].isoformat() if len(equity_curve) else None,
        "bars": int(len(frame)),
        "cumulative_return": cumulative_return,
        "annualized_return": annualized_return,
        "volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown(equity_curve),
        "entries": int(len(trades)),
        "long_entries": int(trades["direction"].eq(1).sum()) if not trades.empty else 0,
        "short_entries": int(trades["direction"].eq(-1).sum()) if not trades.empty else 0,
        "win_rate": float(wins / len(trades)) if len(trades) else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else None,
        "avg_trade_net_return": float(net_returns.mean()) if len(net_returns) else 0.0,
        "median_trade_net_return": float(net_returns.median()) if len(net_returns) else 0.0,
        "fee_rate": config.fee_rate,
    }


def run_backtest(
    frame: pd.DataFrame,
    *,
    symbol: str,
    window_name: str,
    config: StrategyConfig,
) -> tuple[dict[str, float | int | str | None], pd.DataFrame, pd.Series]:
    frame = add_indicators(frame, config)
    equity = 1.0
    position = 0
    entry_price = np.nan
    entry_equity = np.nan
    entry_ts: pd.Timestamp | None = None
    equity_points: list[tuple[pd.Timestamp, float]] = []
    trades: list[dict[str, float | int | str]] = []

    for ts, row in frame.iterrows():
        close = float(row["close"])
        high = float(row["high"])
        low = float(row["low"])
        exited = False

        if position != 0 and entry_ts is not None and ts > entry_ts:
            stop_price = (
                entry_price * (1.0 - config.stop_loss_pct)
                if position > 0
                else entry_price * (1.0 + config.stop_loss_pct)
            )
            take_price = (
                entry_price * (1.0 + config.take_profit_pct)
                if position > 0
                else entry_price * (1.0 - config.take_profit_pct)
            )
            exit_reason = None
            exit_price = np.nan
            if position > 0:
                if low <= stop_price:
                    exit_reason = "stop"
                    exit_price = stop_price
                elif high >= take_price:
                    exit_reason = "take"
                    exit_price = take_price
            else:
                if high >= stop_price:
                    exit_reason = "stop"
                    exit_price = stop_price
                elif low <= take_price:
                    exit_reason = "take"
                    exit_price = take_price

            if exit_reason is not None:
                gross_return = position * config.allocation * (exit_price / entry_price - 1.0)
                exit_equity_before_fee = entry_equity * (1.0 + gross_return)
                equity = exit_equity_before_fee * (1.0 - config.fee_rate * config.allocation)
                trades.append(
                    {
                        "symbol": symbol,
                        "window": window_name,
                        "entry_ts": entry_ts.isoformat(),
                        "exit_ts": ts.isoformat(),
                        "direction": position,
                        "entry_price": float(entry_price),
                        "exit_price": float(exit_price),
                        "exit_reason": exit_reason,
                        "gross_return": float(gross_return),
                        "net_return": float(
                            (1.0 + gross_return)
                            * (1.0 - config.fee_rate * config.allocation) ** 2
                            - 1.0
                        ),
                    }
                )
                position = 0
                entry_price = np.nan
                entry_equity = np.nan
                entry_ts = None
                exited = True

        if position == 0 and not exited:
            valid = not pd.isna(row["rsi"]) and not pd.isna(row["stoch_k"]) and not pd.isna(row["ema_200"])
            if valid:
                long_signal = (
                    row["rsi"] < config.rsi_long_threshold
                    and row["stoch_k"] < config.stochastic_long_threshold
                    and close > row["ema_200"]
                )
                short_signal = (
                    row["rsi"] > config.rsi_short_threshold
                    and row["stoch_k"] > config.stochastic_short_threshold
                    and close < row["ema_200"]
                )
                if long_signal or short_signal:
                    position = 1 if long_signal else -1
                    entry_price = close
                    equity *= 1.0 - config.fee_rate * config.allocation
                    entry_equity = equity
                    entry_ts = ts

        if position != 0:
            mark_return = position * config.allocation * (close / entry_price - 1.0)
            marked_equity = entry_equity * (1.0 + mark_return)
            equity_points.append((ts, float(marked_equity)))
        else:
            equity_points.append((ts, float(equity)))

    if position != 0 and entry_ts is not None:
        ts = frame.index[-1]
        close = float(frame["close"].iloc[-1])
        gross_return = position * config.allocation * (close / entry_price - 1.0)
        exit_equity_before_fee = entry_equity * (1.0 + gross_return)
        equity = exit_equity_before_fee * (1.0 - config.fee_rate * config.allocation)
        trades.append(
            {
                "symbol": symbol,
                "window": window_name,
                "entry_ts": entry_ts.isoformat(),
                "exit_ts": ts.isoformat(),
                "direction": position,
                "entry_price": float(entry_price),
                "exit_price": close,
                "exit_reason": "end",
                "gross_return": float(gross_return),
                "net_return": float(
                    (1.0 + gross_return)
                    * (1.0 - config.fee_rate * config.allocation) ** 2
                    - 1.0
                ),
            }
        )
        equity_points[-1] = (ts, float(equity))

    equity_curve = pd.Series(
        [value for _, value in equity_points],
        index=pd.DatetimeIndex([ts for ts, _ in equity_points], name="ts"),
        name="equity",
    )
    trades_frame = pd.DataFrame(trades)
    summary = summarize(
        symbol=symbol,
        window_name=window_name,
        frame=frame,
        equity_curve=equity_curve,
        trades=trades_frame,
        config=config,
    )
    return summary, trades_frame, equity_curve


def slice_frame(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return frame[(frame.index >= start) & (frame.index <= end)].copy()


def main() -> None:
    symbols = ["BTC/USDT:USDT", "HYPE/USDT:USDT"]
    frames = {symbol: load_ohlcv(symbol) for symbol in symbols}
    common_start = max(frame.index.min() for frame in frames.values())
    common_end = min(frame.index.max() for frame in frames.values())
    windows = {
        "common_full": (common_start, common_end),
        "last_90d": (common_end - pd.Timedelta(days=90), common_end),
    }

    result_rows = []
    all_trades = []
    equity_columns = []
    for fee_name, fee_rate in {"zero_fee": 0.0, "hyperliquid_taker": 0.00045}.items():
        config = StrategyConfig(fee_rate=fee_rate)
        for window_name, (start, end) in windows.items():
            for symbol, frame in frames.items():
                sliced = slice_frame(frame, start, end)
                summary, trades, equity_curve = run_backtest(
                    sliced,
                    symbol=symbol,
                    window_name=f"{window_name}_{fee_name}",
                    config=config,
                )
                summary["fee_model"] = fee_name
                summary["source"] = "data/normalized/ohlcv/binance/perp/15m"
                result_rows.append(summary)
                if not trades.empty:
                    trades["fee_model"] = fee_name
                    all_trades.append(trades)
                equity_columns.append(
                    equity_curve.rename(f"{symbol}_{window_name}_{fee_name}")
                )

    summary_frame = pd.DataFrame(result_rows)
    trades_frame = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    equity_frame = pd.concat(equity_columns, axis=1)

    payload = {
        "strategy": "Optimized BTC Mean Reversion (RSI 20/65)",
        "source_article": "https://x.com/MinaraCN/status/2044620258506625334",
        "assumptions": {
            **asdict(StrategyConfig()),
            "notes": [
                "Rules are reconstructed from the public TradingView strategy description linked in the Minara article.",
                "Stochastic uses raw %K(14); no smoothing was specified on the public page.",
                "Entries are at signal-bar close; stop/take exits are checked from the next bar onward using OHLC high/low with stop-first tie break.",
                "HyperLiquid fee run uses taker fee 0.045% per side and no slippage/funding model, matching the article's fee-only discussion.",
            ],
        },
        "data_coverage": {
            symbol: {
                "start": frame.index.min().isoformat(),
                "end": frame.index.max().isoformat(),
                "bars": int(len(frame)),
            }
            for symbol, frame in frames.items()
        },
        "windows": {
            name: {"start": start.isoformat(), "end": end.isoformat()}
            for name, (start, end) in windows.items()
        },
        "summary": result_rows,
    }
    (REPORT_PREFIX.with_suffix(".json")).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary_frame.to_csv(f"{REPORT_PREFIX}_summary.csv", index=False)
    trades_frame.to_csv(f"{REPORT_PREFIX}_trades.csv", index=False)
    equity_frame.to_csv(f"{REPORT_PREFIX}_equity.csv")

    print(summary_frame.to_string(index=False))
    print(f"wrote {REPORT_PREFIX}.json")


if __name__ == "__main__":
    main()
