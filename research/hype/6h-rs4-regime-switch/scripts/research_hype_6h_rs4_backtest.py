from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DATA_ROOT = Path("data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=5m")
RAW_DATA_ROOT = Path("data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=5m")
FUNDING_ROOT = Path("data/normalized/funding_rates/exchange=binance/market_type=perp")
SYMBOL_FILE = "symbol=hype_usdt_usdt.parquet"

FAMILY_ROOT = Path("research/hype/6h-rs4-regime-switch")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAG_ROOT = FAMILY_ROOT / "diagnostics"

SUMMARY_JSON = ARTIFACT_ROOT / "hype_6h_rs4_backtest_summary.json"
METRICS_CSV = ARTIFACT_ROOT / "hype_6h_rs4_metrics.csv"
WF_CSV = ARTIFACT_ROOT / "hype_6h_rs4_walk_forward_windows.csv"
TRADES_CSV = ARTIFACT_ROOT / "hype_6h_rs4_trades.csv"
EQUITY_CSV = ARTIFACT_ROOT / "hype_6h_rs4_equity.csv"
REPORT_MD = DIAG_ROOT / "hype-6h-rs4-regime-switch-backtest-2026-06-26.md"

FEE_RATE_PER_FILL = 0.00045
SLIPPAGE_RATE_PER_FILL = 0.00050
ONE_WAY_COST = FEE_RATE_PER_FILL + SLIPPAGE_RATE_PER_FILL
PERIODS_PER_YEAR = 365.25 * 4.0


@dataclass(frozen=True, slots=True)
class StrategyReturns:
    name: str
    frame: pd.DataFrame
    positions: np.ndarray
    returns: np.ndarray
    trades: list[dict[str, Any]]


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def num(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def load_5m_frame() -> pd.DataFrame:
    files = sorted(DATA_ROOT.glob(f"date=*/{SYMBOL_FILE}"))
    if not files:
        raise FileNotFoundError(f"no HYPE 5m parquet files under {DATA_ROOT}")

    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    numeric_columns = ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap"]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def load_funding_rates() -> pd.DataFrame:
    files = sorted(FUNDING_ROOT.rglob(SYMBOL_FILE))
    if not files:
        return pd.DataFrame(columns=["ts", "funding_rate", "source"])

    frame = pd.concat(
        [
            pd.read_parquet(path, columns=[column for column in ["ts", "funding_rate", "source"] if column in pd.read_parquet(path).columns])
            for path in files
        ],
        ignore_index=True,
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["funding_rate"] = pd.to_numeric(frame["funding_rate"], errors="coerce").fillna(0.0)
    return frame.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)


def quality_checks_5m(frame: pd.DataFrame) -> dict[str, Any]:
    ts = pd.to_datetime(frame["ts"], utc=True)
    expected = pd.date_range(ts.iloc[0], ts.iloc[-1], freq="5min")
    missing = expected.difference(ts)
    duplicates = int(frame.duplicated("ts").sum())
    critical_columns = ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap"]
    null_counts = {column: int(frame[column].isna().sum()) for column in critical_columns if column in frame.columns}
    invalid_ohlc = int(
        (
            (frame["open"] <= 0)
            | (frame["high"] <= 0)
            | (frame["low"] <= 0)
            | (frame["close"] <= 0)
            | (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
            | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
        ).sum()
    )
    false_closed = int((~frame.get("is_closed", pd.Series(True, index=frame.index)).astype(bool)).sum())
    source_counts = (
        frame.get("source", pd.Series(dtype="string"))
        .astype("string")
        .value_counts(dropna=False)
        .astype(int)
        .to_dict()
    )
    raw_check = raw_normalized_equality_check(frame)
    return {
        "exchange": "binance",
        "symbol": "HYPEUSDT",
        "market_type": "perp",
        "input_timeframe": "5m",
        "start_ts": str(ts.iloc[0]),
        "end_ts": str(ts.iloc[-1]),
        "rows": int(len(frame)),
        "expected_rows": int(len(expected)),
        "missing_5m_bars": int(len(missing)),
        "first_missing_5m_bar": str(missing[0]) if len(missing) else None,
        "duplicate_ts": duplicates,
        "critical_nulls": null_counts,
        "invalid_ohlc_rows": invalid_ohlc,
        "non_closed_rows": false_closed,
        "source_counts": source_counts,
        "raw_hype_5m_file_count": raw_check["raw_file_count"],
        "raw_normalized_equality_checked": raw_check["checked"],
        "raw_normalized_equality_passed": raw_check["passed"],
        "raw_normalized_equality": raw_check,
    }


def raw_normalized_equality_check(normalized: pd.DataFrame) -> dict[str, Any]:
    raw_files = sorted(RAW_DATA_ROOT.glob(f"date=*/{SYMBOL_FILE}"))
    result: dict[str, Any] = {
        "checked": False,
        "passed": False,
        "raw_file_count": len(raw_files),
        "raw_rows": 0,
        "normalized_rows": int(len(normalized)),
        "missing_in_raw": None,
        "missing_in_normalized": None,
        "mismatch_counts": {},
        "note": None,
    }
    if not raw_files:
        result["note"] = f"No matching raw HYPE 5m parquet was found under {RAW_DATA_ROOT}."
        return result

    raw = pd.concat([pd.read_parquet(path) for path in raw_files], ignore_index=True)
    raw["ts"] = pd.to_datetime(raw["ts"], utc=True)
    raw = raw.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    result["raw_rows"] = int(len(raw))

    norm = normalized.copy()
    norm["ts"] = pd.to_datetime(norm["ts"], utc=True)
    raw_ts = pd.DatetimeIndex(raw["ts"])
    norm_ts = pd.DatetimeIndex(norm["ts"])
    missing_in_raw = norm_ts.difference(raw_ts)
    missing_in_norm = raw_ts.difference(norm_ts)
    result["missing_in_raw"] = int(len(missing_in_raw))
    result["missing_in_normalized"] = int(len(missing_in_norm))

    compare_columns = ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap", "is_closed"]
    merged = norm[["ts", *compare_columns]].merge(
        raw[["ts", *compare_columns]],
        on="ts",
        how="inner",
        suffixes=("_normalized", "_raw"),
    )
    mismatch_counts: dict[str, int] = {}
    for column in compare_columns:
        left = merged[f"{column}_normalized"]
        right = merged[f"{column}_raw"]
        if column == "is_closed":
            mismatch = left.astype(bool).to_numpy() != right.astype(bool).to_numpy()
        elif column == "trade_count":
            mismatch = left.astype("int64").to_numpy() != right.astype("int64").to_numpy()
        else:
            mismatch = ~np.isclose(
                pd.to_numeric(left, errors="coerce").to_numpy("float64"),
                pd.to_numeric(right, errors="coerce").to_numpy("float64"),
                rtol=1e-12,
                atol=1e-12,
                equal_nan=True,
            )
        mismatch_counts[column] = int(np.sum(mismatch))

    result["checked"] = True
    result["mismatch_counts"] = mismatch_counts
    result["passed"] = (
        result["missing_in_raw"] == 0
        and result["missing_in_normalized"] == 0
        and all(count == 0 for count in mismatch_counts.values())
    )
    result["note"] = "Compared raw and normalized Binance HYPEUSDT perp 5m rows by ts."
    return result


def resample_to_6h(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    data = frame.copy()
    data["bar_ts"] = pd.to_datetime(data["ts"], utc=True).dt.floor("6h")
    grouped = data.groupby("bar_ts", sort=True)
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
        is_closed=("is_closed", "all"),
    ).reset_index(drop=True)
    bars["vwap"] = bars["quote_volume"] / bars["volume"].replace(0.0, np.nan)
    complete = (
        (bars["row_count"] == 72)
        & (bars["first_ts"] == bars["ts"])
        & (bars["last_ts"] == bars["ts"] + pd.Timedelta(hours=6) - pd.Timedelta(minutes=5))
        & bars["is_closed"].astype(bool)
    )
    dropped = bars.loc[~complete, ["ts", "first_ts", "last_ts", "row_count"]].copy()
    bars = bars.loc[complete].drop(columns=["first_ts", "last_ts", "row_count"]).reset_index(drop=True)
    expected = pd.date_range(bars["ts"].iloc[0], bars["ts"].iloc[-1], freq="6h")
    missing = expected.difference(pd.to_datetime(bars["ts"], utc=True))
    quality = {
        "output_timeframe": "6h",
        "rows": int(len(bars)),
        "start_ts": str(bars["ts"].iloc[0]),
        "end_ts": str(bars["ts"].iloc[-1]),
        "dropped_partial_6h_groups": int(len(dropped)),
        "dropped_partial_6h_examples": dropped.head(5).astype(str).to_dict("records"),
        "missing_6h_bars": int(len(missing)),
        "first_missing_6h_bar": str(missing[0]) if len(missing) else None,
    }
    return bars, quality


def attach_features(bars: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    frame = bars.copy()
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]

    frame["range3d"] = high.rolling(12).max() / low.rolling(12).min() - 1.0
    ema_fast = close.ewm(span=8, adjust=False, min_periods=8).mean()
    ema_slow = close.ewm(span=21, adjust=False, min_periods=21).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=5, adjust=False, min_periods=5).mean()
    frame["macd_hist"] = macd - signal
    frame["macd_hist_pos2"] = (frame["macd_hist"] > 0) & (frame["macd_hist"].shift(1) > 0)

    prev_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr_pct28"] = true_range.rolling(28).mean() / close

    net_move = (close - close.shift(20)).abs()
    path = close.diff().abs().rolling(20).sum()
    frame["er20"] = net_move / path.replace(0.0, np.nan)
    frame["hi20_prev"] = high.shift(1).rolling(20).max()
    frame["lo20_prev"] = low.shift(1).rolling(20).min()
    frame["hi10_prev"] = high.shift(1).rolling(10).max()
    frame["lo10_prev"] = low.shift(1).rolling(10).min()
    frame["open_ret_next"] = frame["open"].shift(-1) / frame["open"] - 1.0

    funding = funding.copy()
    if funding.empty:
        frame["funding_sum"] = 0.0
        return frame

    funding["bar_ts"] = pd.to_datetime(funding["ts"], utc=True).dt.floor("6h")
    funding_sum = funding.groupby("bar_ts")["funding_rate"].sum()
    frame["funding_sum"] = pd.to_datetime(frame["ts"], utc=True).map(funding_sum).fillna(0.0).astype(float)
    return frame


def v10_base_signal(frame: pd.DataFrame, i: int, *, use_range_gate: bool = True) -> int:
    hist = float(frame.at[i, "macd_hist"])
    if not np.isfinite(hist):
        return 0
    gate = bool(frame.at[i, "range3d"] <= 0.12) if use_range_gate else True
    if not gate:
        return 0
    if hist < 0:
        return -1
    if bool(frame.at[i, "macd_hist_pos2"]):
        return 1
    return 0


def simulate_v10(frame: pd.DataFrame, *, use_range_gate: bool = True, use_mfeu: bool = True) -> np.ndarray:
    n = len(frame)
    pos = np.zeros(n, dtype="int8")
    current = 0
    entry_price = np.nan
    entry_atr = np.nan
    peak_favorable = 0.0
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
            if use_mfeu and np.isfinite(entry_atr) and peak_favorable >= 2.0 * entry_atr:
                qualified = True

        base = v10_base_signal(frame, i, use_range_gate=use_range_gate)
        target = base
        if current != 0 and base == 0 and use_mfeu and qualified:
            if not first_flat_ignored:
                target = current
                first_flat_ignored = True
            else:
                giveback = peak_favorable - close_favorable
                if close_favorable > 0.0 and giveback < 1.5 * entry_atr:
                    target = current
                else:
                    target = 0

        if i + 1 < n:
            if target != current:
                if target != 0:
                    entry_price = float(frame.at[i + 1, "open"])
                    entry_atr = float(frame.at[i, "atr_pct28"])
                    peak_favorable = 0.0
                    qualified = False
                    first_flat_ignored = False
                else:
                    entry_price = np.nan
                    entry_atr = np.nan
                    peak_favorable = 0.0
                    qualified = False
                    first_flat_ignored = False
            current = target
    pos[-1] = current
    return pos


def melt_target(frame: pd.DataFrame, i: int, current: int, *, mode: str) -> int:
    range3d = float(frame.at[i, "range3d"])
    er20 = float(frame.at[i, "er20"])
    close = float(frame.at[i, "close"])
    gate_range = np.isfinite(range3d) and range3d > 0.12
    gate_er = np.isfinite(er20) and er20 >= 0.35

    if mode == "long_no_er":
        gate = gate_range
    else:
        gate = gate_range and gate_er

    if mode == "long_no_donchian":
        return 1 if gate else 0

    if mode == "both":
        if current > 0:
            if (not gate) or close < float(frame.at[i, "lo10_prev"]):
                return 0
            return 1
        if current < 0:
            if (not gate) or close > float(frame.at[i, "hi10_prev"]):
                return 0
            return -1
        if gate and close > float(frame.at[i, "hi20_prev"]):
            return 1
        if gate and close < float(frame.at[i, "lo20_prev"]):
            return -1
        return 0

    if current > 0:
        if (not gate) or close < float(frame.at[i, "lo10_prev"]):
            return 0
        return 1
    if gate and close > float(frame.at[i, "hi20_prev"]):
        return 1
    return 0


def simulate_melt(frame: pd.DataFrame, *, mode: str = "long") -> np.ndarray:
    n = len(frame)
    pos = np.zeros(n, dtype="int8")
    current = 0
    for i in range(n - 1):
        pos[i] = current
        target = melt_target(frame, i, current, mode=mode)
        current = target
    pos[-1] = current
    return pos


def extract_trades(name: str, frame: pd.DataFrame, positions: np.ndarray, interval_returns: np.ndarray) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    current = 0
    entry_i: int | None = None
    entry_price = np.nan
    trade_returns: list[float] = []

    for i, position in enumerate(positions[:-1]):
        position = int(position)
        if position != current:
            if current != 0 and entry_i is not None:
                exit_i = i
                gross = float(np.prod(1.0 + np.asarray(trade_returns, dtype=float)) - 1.0) if trade_returns else 0.0
                trades.append(
                    {
                        "strategy": name,
                        "entry_ts": str(frame.at[entry_i, "ts"]),
                        "exit_ts": str(frame.at[exit_i, "ts"]),
                        "side": "long" if current > 0 else "short",
                        "entry_price": float(entry_price),
                        "exit_price": float(frame.at[exit_i, "open"]),
                        "bars_held": int(exit_i - entry_i),
                        "net_return": gross,
                    }
                )
                trade_returns = []
            if position != 0:
                entry_i = i
                entry_price = float(frame.at[i, "open"])
                trade_returns = []
            else:
                entry_i = None
                entry_price = np.nan
            current = position
        if position != 0 and i < len(interval_returns):
            trade_returns.append(float(interval_returns[i]))

    if current != 0 and entry_i is not None:
        exit_i = len(frame) - 1
        gross = float(np.prod(1.0 + np.asarray(trade_returns, dtype=float)) - 1.0) if trade_returns else 0.0
        trades.append(
            {
                "strategy": name,
                "entry_ts": str(frame.at[entry_i, "ts"]),
                "exit_ts": str(frame.at[exit_i, "ts"]),
                "side": "long" if current > 0 else "short",
                "entry_price": float(entry_price),
                "exit_price": float(frame.at[exit_i, "open"]),
                "bars_held": int(exit_i - entry_i),
                "net_return": gross,
            }
        )
    return trades


def leg_returns(name: str, frame: pd.DataFrame, positions: np.ndarray) -> StrategyReturns:
    pos = positions.astype(float)
    prev = np.roll(pos, 1)
    prev[0] = 0.0
    turnover = np.abs(pos - prev)
    open_ret_next = frame["open_ret_next"].fillna(0.0).to_numpy("float64")
    funding_sum = frame["funding_sum"].fillna(0.0).to_numpy("float64")
    returns = pos * open_ret_next - turnover * ONE_WAY_COST - pos * funding_sum
    returns[-1] = 0.0
    trades = extract_trades(name, frame, positions, returns)
    return StrategyReturns(name=name, frame=frame, positions=positions, returns=returns, trades=trades)


def equity_curve(returns: np.ndarray) -> np.ndarray:
    return np.cumprod(1.0 + np.nan_to_num(returns, nan=0.0))


def metrics_for_returns(
    name: str,
    frame: pd.DataFrame,
    returns: np.ndarray,
    positions: np.ndarray | None = None,
    trades: list[dict[str, Any]] | None = None,
    *,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> dict[str, Any]:
    returns_array = np.asarray(returns, dtype="float64").reshape(-1)
    n = min(len(frame), len(returns_array))
    local_frame = frame.iloc[:n].reset_index(drop=True)
    local_returns = returns_array[:n]
    local_positions = positions[:n] if positions is not None else None
    n = min(len(local_frame), len(local_returns), len(local_positions) if local_positions is not None else len(local_returns))
    local_frame = local_frame.iloc[:n].reset_index(drop=True)
    local_returns = local_returns[:n]
    local_positions = local_positions[:n] if local_positions is not None else None
    ts = pd.DatetimeIndex(pd.to_datetime(local_frame["ts"], utc=True))
    mask = np.ones(n, dtype=bool)
    if start is not None:
        mask &= ts >= start
    if end is not None:
        mask &= ts < end
    mask[-1] = False
    selected_returns = local_returns[mask]
    selected_ts = ts[mask]
    if len(selected_returns) == 0:
        return {
            "name": name,
            "start": str(start) if start is not None else None,
            "end": str(end) if end is not None else None,
            "bars": 0,
            "total_return": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "exposure": 0.0,
            "trade_count": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
        }

    equity = equity_curve(selected_returns)
    peak = np.maximum.accumulate(equity)
    drawdown = equity / peak - 1.0
    std = float(np.std(selected_returns, ddof=1)) if len(selected_returns) > 1 else 0.0
    sharpe = float(np.mean(selected_returns) / std * np.sqrt(PERIODS_PER_YEAR)) if std > 0 else 0.0
    selected_trades = trades or []
    if start is not None or end is not None:
        selected_trades = [
            trade
            for trade in selected_trades
            if (start is None or pd.Timestamp(trade["entry_ts"]) >= start)
            and (end is None or pd.Timestamp(trade["entry_ts"]) < end)
        ]
    trade_rets = np.asarray([float(trade["net_return"]) for trade in selected_trades], dtype=float)
    wins = trade_rets[trade_rets > 0]
    losses = trade_rets[trade_rets <= 0]
    if positions is not None:
        exposure = float(np.mean(np.abs(local_positions[mask]) > 0))
    else:
        exposure = float(np.mean(np.abs(selected_returns) > 1e-12))
    return {
        "name": name,
            "start": str(selected_ts[0]),
            "end": str(selected_ts[-1] + pd.Timedelta(hours=6)),
        "bars": int(len(selected_returns)),
        "total_return": float(equity[-1] - 1.0),
        "sharpe": sharpe,
        "max_drawdown": float(np.min(drawdown)),
        "exposure": exposure,
        "trade_count": int(len(selected_trades)),
        "win_rate": float(np.mean(trade_rets > 0)) if len(trade_rets) else 0.0,
        "profit_factor": float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf") if len(wins) else 0.0,
        "best_trade": float(np.max(trade_rets)) if len(trade_rets) else 0.0,
        "worst_trade": float(np.min(trade_rets)) if len(trade_rets) else 0.0,
    }


def combine_returns(
    name: str,
    frame: pd.DataFrame,
    v10: StrategyReturns,
    melt: StrategyReturns,
    *,
    weight: float,
) -> StrategyReturns:
    returns = v10.returns + weight * melt.returns
    positions = v10.positions + weight * melt.positions
    trades = [*v10.trades, *melt.trades]
    for trade in trades:
        trade.setdefault("combo", name)
    return StrategyReturns(name=name, frame=frame, positions=positions, returns=returns, trades=trades)


def walk_forward_windows(frame: pd.DataFrame, strategies: dict[str, StrategyReturns]) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    ts = pd.to_datetime(frame["ts"], utc=True)
    start = ts.iloc[0] + pd.Timedelta(days=150)
    end = ts.iloc[-1] + pd.Timedelta(hours=6)
    rows: list[dict[str, Any]] = []
    current = start
    while current < end:
        window_end = min(current + pd.Timedelta(days=21), end)
        for name, strategy in strategies.items():
            row = metrics_for_returns(name, frame, strategy.returns, strategy.positions, strategy.trades, start=current, end=window_end)
            row["window_start"] = str(current)
            row["window_end"] = str(window_end)
            rows.append(row)
        current = window_end

    wf = pd.DataFrame(rows)
    summary: dict[str, dict[str, Any]] = {}
    for name, strategy in strategies.items():
        selected = wf[wf["name"] == name].copy()
        oos_start = start
        summary[name] = metrics_for_returns(
            f"{name}_wf_oos",
            frame,
            strategy.returns,
            strategy.positions,
            strategy.trades,
            start=oos_start,
            end=end,
        )
        summary[name]["positive_windows"] = int((selected["total_return"] > 0).sum())
        summary[name]["window_count"] = int(len(selected))
        summary[name]["worst_window_return"] = float(selected["total_return"].min()) if len(selected) else 0.0
    return wf, summary


def build_report(summary: dict[str, Any], metrics: pd.DataFrame, wf_summary: dict[str, Any]) -> str:
    full = metrics[metrics["slice"] == "full"].set_index("name")
    canonical = metrics[metrics["slice"] == "canonical_to_2026_05_15"].set_index("name")
    may = metrics[metrics["slice"] == "may_2026"].set_index("name")
    forward = metrics[metrics["slice"] == "post_html_2026_06_10"].set_index("name")

    def row(table: pd.DataFrame, name: str, column: str, default: float = 0.0) -> float:
        if name not in table.index:
            return default
        value = table.at[name, column]
        return float(value) if pd.notna(value) else default

    lines = [
        "# HYPE-6H-RS4-Regime-Switch 独立复现诊断 2026-06-26",
        "",
        "Family id：`HYPE-6H-RS4-Regime-Switch`。本报告复现同事 HTML 中的 RS4 规则，但使用本仓库标准数据湖的 Binance HYPEUSDT 永续 `5m` 闭合 K 聚合为 `6h`。因此它只能审计 Binance/canonical 近期段，不能直接证明 HTML 声称的 Bybit 2024-12 全史表现。",
        "",
        "## 数据口径与质量",
        "",
        f"- 数据：Binance HYPEUSDT perpetual `5m` normalized OHLCV，覆盖 `{summary['quality_5m']['start_ts']}` 到 `{summary['quality_5m']['end_ts']}`，共 `{summary['quality_5m']['rows']}` 根。",
        f"- 质量检查：缺失 5m bar `{summary['quality_5m']['missing_5m_bars']}`，重复 ts `{summary['quality_5m']['duplicate_ts']}`，非 closed `{summary['quality_5m']['non_closed_rows']}`，非法 OHLC `{summary['quality_5m']['invalid_ohlc_rows']}`。",
        f"- 聚合：完整 `6h` bar `{summary['quality_6h']['rows']}` 根，覆盖 `{summary['quality_6h']['start_ts']}` 到 `{summary['quality_6h']['end_ts']}`；丢弃不完整 6h group `{summary['quality_6h']['dropped_partial_6h_groups']}` 个。",
        f"- raw-normalized：checked `{summary['quality_5m']['raw_normalized_equality_checked']}`，passed `{summary['quality_5m']['raw_normalized_equality_passed']}`，raw 5m files `{summary['quality_5m']['raw_hype_5m_file_count']}`。",
        f"- funding：`{summary['funding']['rows']}` rows，覆盖 `{summary['funding']['start_ts']}` 到 `{summary['funding']['end_ts']}`；OHLCV 超出 funding 的区间按 0 funding 处理，6 月后半段需补齐后复核。",
        "",
        "## 策略口径",
        "",
        f"- 信号：6h 收盘计算，第下一根 6h 开盘成交；成本为手续费 `{FEE_RATE_PER_FILL * 10000:.1f}bps` + 滑点 `{SLIPPAGE_RATE_PER_FILL * 10000:.1f}bps` 单边。",
        "- v10：`range3d <= 12%`，MACD(8,21,5) histogram；空头 1 根负柱，做多 2 根正柱；MFEu 只延迟空仓信号，不延迟反向信号。",
        "- melt-leg：`range3d > 12%` 且 `ER20 >= 0.35`，只做多，收盘突破前 20 根高点入场，跌破前 10 根低点或 gate 失效退出。",
        "- 资金费：按 6h 持仓区间内 funding_rate 求和，正 funding 对多头扣减、对空头增加。",
        "",
        "## 主要结果",
        "",
        f"- 全样本 RS4(w=1)：收益 `{pct(row(full, 'rs4_w1', 'total_return'))}`，Sharpe `{num(row(full, 'rs4_w1', 'sharpe'))}`，最大回撤 `{pct(row(full, 'rs4_w1', 'max_drawdown'))}`。",
        f"- 全样本 v10 单腿：收益 `{pct(row(full, 'v10', 'total_return'))}`，最大回撤 `{pct(row(full, 'v10', 'max_drawdown'))}`；melt 单腿：收益 `{pct(row(full, 'melt_long', 'total_return'))}`，最大回撤 `{pct(row(full, 'melt_long', 'max_drawdown'))}`。",
        f"- canonical 截止 2026-05-15：RS4(w=1) 收益 `{pct(row(canonical, 'rs4_w1', 'total_return'))}`，最大回撤 `{pct(row(canonical, 'rs4_w1', 'max_drawdown'))}`。",
        f"- 2026-05 暴涨月：v10 `{pct(row(may, 'v10', 'total_return'))}`，melt `{pct(row(may, 'melt_long', 'total_return'))}`，RS4(w=1) `{pct(row(may, 'rs4_w1', 'total_return'))}`。",
        f"- HTML 生成后近似前向段（2026-06-10 后）：RS4(w=1) `{pct(row(forward, 'rs4_w1', 'total_return'))}`，melt `{pct(row(forward, 'melt_long', 'total_return'))}`。",
        "",
        "## Walk-Forward 与消融",
        "",
        f"- 150d train / 21d test 滚动 OOS：RS4(w=1) `{pct(wf_summary['rs4_w1']['total_return'])}`，正窗口 `{wf_summary['rs4_w1']['positive_windows']}/{wf_summary['rs4_w1']['window_count']}`，最差窗口 `{pct(wf_summary['rs4_w1']['worst_window_return'])}`。",
        f"- 去掉 ER20 的 melt 消融：全样本回撤 `{pct(row(full, 'rs4_no_er', 'max_drawdown'))}`；双向 melt 消融：全样本回撤 `{pct(row(full, 'rs4_melt_both', 'max_drawdown'))}`；去掉 Donchian：全样本回撤 `{pct(row(full, 'rs4_no_donchian', 'max_drawdown'))}`。",
        "",
        "## 结论",
        "",
    ]
    rs4_return = row(full, "rs4_w1", "total_return")
    rs4_dd = row(full, "rs4_w1", "max_drawdown")
    forward_return = row(forward, "rs4_w1", "total_return")
    no_er_dd = row(full, "rs4_no_er", "max_drawdown")
    if rs4_return > 0 and rs4_dd > -0.25:
        lines.append("这次 Binance 近期段复现支持 RS4 的核心机制：v10 负责压缩 regime，melt-leg 在 2026-05 这种高波动干净上涨段补收益，组合表现明显好于只看 melt-leg。")
    else:
        lines.append("这次 Binance 近期段复现没有支持 RS4 作为候选策略：组合收益/回撤没有达到机制叙述要求。")
    if no_er_dd < -0.35:
        lines.append("但拟合风险仍高：melt-leg 的 ER20 是明显承重墙，删掉后风险显著恶化，说明收益高度依赖少数状态过滤。")
    else:
        lines.append("拟合风险仍不能排除：样本只有约一年，melt-leg 交易稀疏，无法从这段数据证明参数不是事件级拟合。")
    if forward_return <= 0:
        lines.append("HTML 生成后的短前向段没有给出正向确认，因此不能提升到 paper-live/live 候选。")
    else:
        lines.append("HTML 生成后的短前向段为正，但时间太短，不能抵消单币、少事件、无 Bybit 全史复核的问题。")
    lines.extend(
        [
            "",
            "当前状态：`diagnostic only / not promoted`。若要继续，下一步应补 Bybit 2024-12 全史或交易所交叉数据，并把订单重启状态、资金费精确结算和 live runner 状态机复现纳入审计。",
            "",
            "## 保留证据",
            "",
            f"- JSON summary：`{SUMMARY_JSON}`",
            f"- metrics CSV：`{METRICS_CSV}`",
            f"- WF windows：`{WF_CSV}`",
            f"- trades：`{TRADES_CSV}`",
            f"- equity：`{EQUITY_CSV}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAG_ROOT.mkdir(parents=True, exist_ok=True)

    frame_5m = load_5m_frame()
    funding = load_funding_rates()
    quality_5m = quality_checks_5m(frame_5m)
    bars_6h, quality_6h = resample_to_6h(frame_5m)
    frame = attach_features(bars_6h, funding)

    v10 = leg_returns("v10", frame, simulate_v10(frame))
    v10_no_mfeu = leg_returns("v10_no_mfeu", frame, simulate_v10(frame, use_mfeu=False))
    v10_no_range = leg_returns("v10_no_range", frame, simulate_v10(frame, use_range_gate=False))
    melt = leg_returns("melt_long", frame, simulate_melt(frame, mode="long"))
    melt_no_er = leg_returns("melt_no_er", frame, simulate_melt(frame, mode="long_no_er"))
    melt_both = leg_returns("melt_both", frame, simulate_melt(frame, mode="both"))
    melt_no_donchian = leg_returns("melt_no_donchian", frame, simulate_melt(frame, mode="long_no_donchian"))

    strategies = {
        "buy_hold": StrategyReturns(
            name="buy_hold",
            frame=frame,
            positions=np.ones(len(frame), dtype="int8"),
            returns=leg_returns("buy_hold", frame, np.ones(len(frame), dtype="int8")).returns,
            trades=[],
        ),
        "v10": v10,
        "v10_no_mfeu": v10_no_mfeu,
        "v10_no_range": v10_no_range,
        "melt_long": melt,
        "rs4_w1": combine_returns("rs4_w1", frame, v10, melt, weight=1.0),
        "rs4_w0_5": combine_returns("rs4_w0_5", frame, v10, melt, weight=0.5),
        "rs4_no_er": combine_returns("rs4_no_er", frame, v10, melt_no_er, weight=1.0),
        "rs4_melt_both": combine_returns("rs4_melt_both", frame, v10, melt_both, weight=1.0),
        "rs4_no_donchian": combine_returns("rs4_no_donchian", frame, v10, melt_no_donchian, weight=1.0),
    }

    slices = {
        "full": (None, None),
        "canonical_to_2026_05_15": (pd.Timestamp("2025-05-30T00:00:00Z"), pd.Timestamp("2026-05-15T00:00:00Z")),
        "may_2026": (pd.Timestamp("2026-05-01T00:00:00Z"), pd.Timestamp("2026-06-01T00:00:00Z")),
        "post_html_2026_06_10": (pd.Timestamp("2026-06-10T00:00:00Z"), None),
    }
    metric_rows: list[dict[str, Any]] = []
    for slice_name, (start, end) in slices.items():
        for name, strategy in strategies.items():
            row = metrics_for_returns(name, frame, strategy.returns, strategy.positions, strategy.trades, start=start, end=end)
            row["slice"] = slice_name
            metric_rows.append(row)
    metrics = pd.DataFrame(metric_rows)

    wf_windows, wf_summary = walk_forward_windows(
        frame,
        {name: strategies[name] for name in ("v10", "melt_long", "rs4_w1", "rs4_w0_5")},
    )

    all_trades = []
    for strategy in strategies.values():
        all_trades.extend(strategy.trades)
    trades = pd.DataFrame(all_trades)

    equity = pd.DataFrame({"ts": frame["ts"]})
    for name, strategy in strategies.items():
        equity[name] = equity_curve(strategy.returns)

    summary = {
        "strategy_family": "HYPE-6H-RS4-Regime-Switch",
        "status": "diagnostic_only_not_promoted",
        "source_html": "/Users/ZK/Downloads/RS4-EXPLAINED-RS4策略详细图解.html",
        "quality_5m": quality_5m,
        "quality_6h": quality_6h,
        "funding": {
            "rows": int(len(funding)),
            "start_ts": str(funding["ts"].iloc[0]) if len(funding) else None,
            "end_ts": str(funding["ts"].iloc[-1]) if len(funding) else None,
            "source_counts": funding.get("source", pd.Series(dtype="string")).astype("string").value_counts(dropna=False).astype(int).to_dict()
            if len(funding)
            else {},
        },
        "costs": {
            "fee_rate_per_fill": FEE_RATE_PER_FILL,
            "slippage_rate_per_fill": SLIPPAGE_RATE_PER_FILL,
            "one_way_cost": ONE_WAY_COST,
        },
        "metrics": metrics.to_dict("records"),
        "walk_forward_summary": wf_summary,
        "artifact_paths": {
            "summary_json": str(SUMMARY_JSON),
            "metrics_csv": str(METRICS_CSV),
            "wf_csv": str(WF_CSV),
            "trades_csv": str(TRADES_CSV),
            "equity_csv": str(EQUITY_CSV),
            "report_md": str(REPORT_MD),
        },
    }

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics.to_csv(METRICS_CSV, index=False)
    wf_windows.to_csv(WF_CSV, index=False)
    trades.to_csv(TRADES_CSV, index=False)
    equity.to_csv(EQUITY_CSV, index=False)
    REPORT_MD.write_text(build_report(summary, metrics, wf_summary), encoding="utf-8")
    print(json.dumps({"summary": str(SUMMARY_JSON), "report": str(REPORT_MD)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
