from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/15m-trend-continuation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
AUDIT_PATH = ARTIFACT_DIR / "btc_binance_15m_long_data_quality_latest.json"
OHLCV_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
FUNDING_ROOT = ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
SYMBOL_FILE = "symbol=btc_usdt_usdt.parquet"

DATE = "2026-07-20"
CANDIDATES_PATH = ARTIFACT_DIR / f"btc_15m_lvcb_candidates_{DATE}.csv"
SUMMARY_PATH = ARTIFACT_DIR / f"btc_15m_lvcb_summary_{DATE}.json"
TRADES_PATH = ARTIFACT_DIR / f"btc_15m_lvcb_selected_trades_{DATE}.csv"
WINDOWS_PATH = ARTIFACT_DIR / f"btc_15m_lvcb_rolling_windows_{DATE}.csv"

BAR = pd.Timedelta(minutes=15)
FEE_PER_FILL = 0.001
SLIPPAGE_PER_FILL = 0.0004
TRAIN_START = pd.Timestamp("2020-01-01T00:00:00Z")
VALIDATION_START = pd.Timestamp("2022-01-01T00:00:00Z")
DIAGNOSTIC_START = pd.Timestamp("2024-01-01T00:00:00Z")

COMPRESSION_QUANTILES = (0.25, 0.30, 0.35, 0.40)
COMPRESSION_LOOKBACKS = (16, 32, 64)
BREAKOUT_WINDOWS = (96, 192)
EMA_PAIRS = ((96, 384),)
SLOPE_LAGS = (16,)
ATR_CAPS = (0.00325, 0.00350, 0.00375, 0.00400, 0.00425)
EXIT_PROFILES = (
    (3.0, 96),
    (3.0, 192),
    (3.0, 384),
    (4.0, 96),
    (4.0, 192),
    (4.0, 384),
    (5.0, 96),
    (5.0, 192),
    (5.0, 384),
)


@dataclass(frozen=True, slots=True)
class SignalConfig:
    compression_quantile: float
    compression_lookback: int
    breakout_window: int
    ema_fast: int
    ema_slow: int
    slope_lag: int
    atr_cap: float


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    signal: SignalConfig
    stop_atr: float
    max_hold_bars: int
    side_mode: str = "long"
    fee_per_fill: float = FEE_PER_FILL
    slippage_per_fill: float = SLIPPAGE_PER_FILL


@dataclass(frozen=True, slots=True)
class SimulationResult:
    metrics: dict[str, Any]
    trades: pd.DataFrame
    equity: pd.Series


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def payload_sha256(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "payload_sha256"}
    return sha256_bytes(canonical_json_bytes(body))


def finite(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isfinite(number):
            return number
        return "inf" if number > 0 else "-inf"
    return value


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    complete = finite(payload)
    complete["payload_sha256"] = payload_sha256(complete)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(complete, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def date_paths(root: Path, start: pd.Timestamp, end: pd.Timestamp) -> list[Path]:
    dates = pd.date_range(
        start.normalize(),
        (end - pd.Timedelta(nanoseconds=1)).normalize(),
        freq="1D",
    )
    paths = [root / f"date={date:%Y-%m-%d}" / SYMBOL_FILE for date in dates]
    missing = [path for path in paths if not path.exists()]
    if missing:
        sample = ", ".join(str(path.relative_to(ROOT)) for path in missing[:3])
        raise FileNotFoundError(f"missing BTC data partitions: {sample}")
    return paths


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if audit.get("total_blocker_count") != 0:
        raise RuntimeError("BTC long-history audit has blockers")
    start = pd.Timestamp(audit["research_start"])
    end = pd.Timestamp(audit["closed_bar_cutoff_exclusive"])
    market_columns = [
        "ts",
        "exchange",
        "symbol",
        "market_type",
        "timeframe",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "is_closed",
        "source",
    ]
    market = pd.concat(
        [
            pd.read_parquet(path, columns=market_columns)
            for path in date_paths(OHLCV_ROOT, start, end)
        ],
        ignore_index=True,
    )
    market["ts"] = pd.to_datetime(market["ts"], utc=True)
    market = (
        market.loc[(market["ts"] >= start) & (market["ts"] < end)]
        .sort_values("ts")
        .reset_index(drop=True)
    )
    funding_columns = [
        "ts",
        "exchange",
        "symbol",
        "market_type",
        "funding_rate",
        "source",
    ]
    funding = pd.concat(
        [
            pd.read_parquet(path, columns=funding_columns)
            for path in date_paths(FUNDING_ROOT, start, end)
        ],
        ignore_index=True,
    )
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = (
        funding.loc[(funding["ts"] >= start) & (funding["ts"] < end)]
        .sort_values("ts")
        .reset_index(drop=True)
    )
    expected = pd.date_range(start, end - BAR, freq=BAR)
    checks = {
        "market_rows": len(market) == len(expected),
        "market_continuity": pd.DatetimeIndex(market["ts"]).equals(expected),
        "market_duplicates": not market["ts"].duplicated().any(),
        "market_closed": bool(market["is_closed"].all()),
        "market_identity": bool(
            market["exchange"].eq("binance").all()
            and market["symbol"].eq("BTC/USDT:USDT").all()
            and market["market_type"].eq("perp").all()
            and market["timeframe"].eq("15m").all()
        ),
        "market_nulls": not market[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
                "vwap",
            ]
        ]
        .isna()
        .any()
        .any(),
        "funding_nonempty": not funding.empty,
        "funding_duplicates": not funding["ts"].duplicated().any(),
        "funding_gap": bool(
            funding["ts"].diff().dropna().max() <= pd.Timedelta(hours=8)
        ),
        "funding_nulls": not funding[["ts", "funding_rate", "source"]]
        .isna()
        .any()
        .any(),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"BTC trend data checks failed: {failed}")
    metadata = {
        "audit_path": str(AUDIT_PATH.relative_to(ROOT)),
        "audit_sha256": sha256_bytes(AUDIT_PATH.read_bytes()),
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "market_rows": len(market),
        "funding_rows": len(funding),
        "checks": checks,
    }
    return market.set_index("ts"), funding, metadata


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(
        alpha=2.0 / (window + 1.0),
        adjust=False,
        min_periods=window,
    ).mean()


def wilder_atr(frame: pd.DataFrame, window: int = 96) -> pd.Series:
    previous = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(
        alpha=1.0 / window,
        adjust=False,
        min_periods=window,
    ).mean()


def funding_cumulative(
    index: pd.DatetimeIndex,
    funding: pd.DataFrame,
) -> np.ndarray:
    funding_ns = pd.DatetimeIndex(funding["ts"]).asi8
    rates = pd.to_numeric(funding["funding_rate"], errors="raise").to_numpy(float)
    cumulative = np.concatenate(([0.0], np.cumsum(rates)))
    locations = np.searchsorted(funding_ns, index.asi8, side="right")
    return cumulative[locations]


def base_features(frame: pd.DataFrame) -> dict[str, Any]:
    close = frame["close"]
    atr = wilder_atr(frame, 96)
    atr_pct = atr / close
    rolling = 90 * 24 * 4
    minimum = 60 * 24 * 4
    return {
        "atr": atr,
        "atr_pct": atr_pct,
        "compression_thresholds": {
            quantile: atr_pct.rolling(rolling, min_periods=minimum)
            .quantile(quantile)
            .shift(1)
            for quantile in COMPRESSION_QUANTILES
        },
        "donchian_highs": {
            window: frame["high"].rolling(window, min_periods=window).max().shift(1)
            for window in BREAKOUT_WINDOWS
        },
        "donchian_lows": {
            window: frame["low"].rolling(window, min_periods=window).min().shift(1)
            for window in BREAKOUT_WINDOWS
        },
        "emas": {
            window: ema(close, window)
            for window in sorted({value for pair in EMA_PAIRS for value in pair})
        },
    }


def signal_universe() -> list[SignalConfig]:
    universe = [
        SignalConfig(
            compression_quantile=quantile,
            compression_lookback=lookback,
            breakout_window=breakout,
            ema_fast=ema_pair[0],
            ema_slow=ema_pair[1],
            slope_lag=slope_lag,
            atr_cap=atr_cap,
        )
        for quantile, lookback, breakout, ema_pair, slope_lag, atr_cap in product(
            COMPRESSION_QUANTILES,
            COMPRESSION_LOOKBACKS,
            BREAKOUT_WINDOWS,
            EMA_PAIRS,
            SLOPE_LAGS,
            ATR_CAPS,
        )
    ]
    if len(universe) != 120:
        raise AssertionError(f"signal universe mismatch: {len(universe)}")
    return universe


def build_signals(
    frame: pd.DataFrame,
    features: dict[str, Any],
    config: SignalConfig,
) -> tuple[np.ndarray, np.ndarray]:
    close = frame["close"]
    atr_pct = features["atr_pct"]
    compression = atr_pct.lt(
        features["compression_thresholds"][config.compression_quantile]
    )
    compressed_recently = (
        compression.rolling(config.compression_lookback, min_periods=1)
        .max()
        .shift(1)
        .fillna(0.0)
        .gt(0.0)
    )
    fast = features["emas"][config.ema_fast]
    slow = features["emas"][config.ema_slow]
    long_regime = fast.gt(slow) & slow.gt(slow.shift(config.slope_lag))
    short_regime = fast.lt(slow) & slow.lt(slow.shift(config.slope_lag))
    volatility_allowed = atr_pct.le(config.atr_cap)
    long_signal = (
        compressed_recently
        & volatility_allowed
        & close.gt(features["donchian_highs"][config.breakout_window])
        & long_regime
    )
    short_signal = (
        compressed_recently
        & volatility_allowed
        & close.lt(features["donchian_lows"][config.breakout_window])
        & short_regime
    )
    return (
        long_signal.fillna(False).to_numpy(bool),
        short_signal.fillna(False).to_numpy(bool),
    )


def adverse_fill(
    raw_price: float,
    direction: int,
    *,
    is_entry: bool,
    slippage: float,
) -> float:
    order_side = direction if is_entry else -direction
    return raw_price * (1.0 + order_side * slippage)


def profit_factor(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    values = pd.to_numeric(trades["trade_return"], errors="coerce").dropna()
    gains = float(values.loc[values > 0.0].sum())
    losses = abs(float(values.loc[values < 0.0].sum()))
    if losses == 0.0:
        return float("inf") if gains > 0.0 else 0.0
    return gains / losses


def metrics(
    equity: pd.Series,
    trades: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    values = np.concatenate(([1.0], equity.to_numpy(float)))
    drawdown = values / np.maximum.accumulate(values) - 1.0
    returns = equity.pct_change().fillna(equity.iloc[0] - 1.0)
    volatility = float(returns.std(ddof=0))
    positive = (
        trades["trade_return"].loc[trades["trade_return"] > 0.0].sort_values(
            ascending=False
        )
        if not trades.empty
        else pd.Series(dtype=float)
    )
    positive_total = float(positive.sum())
    top_one = 1.0 if positive_total <= 0.0 else float(positive.iloc[:1].sum() / positive_total)
    top_three = (
        1.0
        if positive_total <= 0.0
        else float(positive.iloc[:3].sum() / positive_total)
    )
    duration_years = (end - start).total_seconds() / (365.0 * 24.0 * 3600.0)
    ending = float(equity.iloc[-1])
    annual_return = (
        ending ** (1.0 / duration_years) - 1.0 if ending > 0.0 else -1.0
    )
    return {
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "return_pct": (ending - 1.0) * 100.0,
        "annual_return_pct": annual_return * 100.0,
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "sharpe": float(
            0.0
            if volatility == 0.0
            else returns.mean() / volatility * math.sqrt(365.0 * 24.0 * 4.0)
        ),
        "trades": len(trades),
        "win_rate": float(
            0.0 if trades.empty else trades["trade_return"].gt(0.0).mean()
        ),
        "profit_factor": float(profit_factor(trades)),
        "long_trades": int(
            0 if trades.empty else trades["direction"].eq("long").sum()
        ),
        "short_trades": int(
            0 if trades.empty else trades["direction"].eq("short").sum()
        ),
        "top_trade_positive_pnl_share": top_one,
        "top3_trade_positive_pnl_share": top_three,
    }


def simulate(
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    long_signal: np.ndarray,
    short_signal: np.ndarray,
    config: StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    label: str,
) -> SimulationResult:
    index = frame.index
    start_i = int(index.searchsorted(start))
    end_i = int(index.searchsorted(end))
    open_ = frame["open"].to_numpy(float)
    low = frame["low"].to_numpy(float)
    high = frame["high"].to_numpy(float)
    close = frame["close"].to_numpy(float)
    realized_equity = 1.0
    position: dict[str, Any] | None = None
    pending_direction = 0
    pending_atr = math.nan
    trades: list[dict[str, Any]] = []
    curve_index: list[pd.Timestamp] = []
    curve_values: list[float] = []

    def close_position(i: int, raw_exit: float, reason: str) -> None:
        nonlocal realized_equity, position
        if position is None:
            raise AssertionError("cannot close empty position")
        direction = int(position["direction"])
        exit_fill = adverse_fill(
            raw_exit,
            direction,
            is_entry=False,
            slippage=config.slippage_per_fill,
        )
        ratio = exit_fill / float(position["entry_fill"])
        funding_return = -direction * (
            funding_path[i] - float(position["funding_at_entry"])
        )
        trade_return = (
            direction * (ratio - 1.0)
            - config.fee_per_fill
            - ratio * config.fee_per_fill
            + funding_return
        )
        equity_before = float(position["equity_before"])
        equity_after = equity_before * (1.0 + trade_return)
        trades.append(
            {
                "label": label,
                "direction": "long" if direction == 1 else "short",
                "signal_ts": position["signal_ts"],
                "entry_ts": position["entry_ts"],
                "exit_ts": index[i],
                "entry_fill": position["entry_fill"],
                "exit_fill": exit_fill,
                "signal_atr": position["signal_atr"],
                "exit_reason": reason,
                "hold_bars": i - int(position["entry_i"]),
                "funding_return": funding_return,
                "trade_return": trade_return,
                "equity_before": equity_before,
                "equity_after": equity_after,
            }
        )
        realized_equity = equity_after
        position = None

    for i in range(start_i, end_i):
        if position is None and pending_direction:
            entry_fill = adverse_fill(
                open_[i],
                pending_direction,
                is_entry=True,
                slippage=config.slippage_per_fill,
            )
            position = {
                "direction": pending_direction,
                "signal_ts": index[i - 1],
                "entry_i": i,
                "entry_ts": index[i],
                "entry_fill": entry_fill,
                "signal_atr": pending_atr,
                "stop": entry_fill
                - pending_direction * config.stop_atr * pending_atr,
                "funding_at_entry": funding_path[i],
                "equity_before": realized_equity,
            }
            pending_direction = 0
            pending_atr = math.nan

        if position is not None:
            direction = int(position["direction"])
            stop = float(position["stop"])
            hold_bars = i - int(position["entry_i"])
            reason: str | None = None
            raw_exit = math.nan
            if hold_bars >= config.max_hold_bars:
                reason = "time_open"
                raw_exit = open_[i]
            elif direction == 1:
                if open_[i] <= stop:
                    reason = "stop_gap"
                    raw_exit = open_[i]
                elif low[i] <= stop:
                    reason = "stop"
                    raw_exit = stop
            else:
                if open_[i] >= stop:
                    reason = "stop_gap"
                    raw_exit = open_[i]
                elif high[i] >= stop:
                    reason = "stop"
                    raw_exit = stop
            if reason is not None:
                close_position(i, raw_exit, reason)

        if position is None:
            if config.side_mode in {"long", "both"} and long_signal[i]:
                pending_direction = 1
                pending_atr = atr[i]
            elif config.side_mode in {"short", "both"} and short_signal[i]:
                pending_direction = -1
                pending_atr = atr[i]

        if position is None:
            marked = realized_equity
        else:
            direction = int(position["direction"])
            ratio = close[i] / float(position["entry_fill"])
            open_return = (
                direction * (ratio - 1.0)
                - config.fee_per_fill
                - direction
                * (funding_path[i] - float(position["funding_at_entry"]))
            )
            marked = float(position["equity_before"]) * (1.0 + open_return)
        curve_index.append(index[i])
        curve_values.append(marked)

    if position is not None:
        final_i = end_i - 1
        close_position(final_i, close[final_i], "window_end")
        curve_values[-1] = realized_equity
    equity = pd.Series(curve_values, index=pd.DatetimeIndex(curve_index), name=label)
    trades_frame = pd.DataFrame(trades)
    return SimulationResult(
        metrics=metrics(equity, trades_frame, start, end),
        trades=trades_frame,
        equity=equity,
    )


def strategy_id(config: StrategyConfig) -> str:
    return "lvcb-" + sha256_bytes(canonical_json_bytes(asdict(config)))[:12]


def development_gate(
    train: dict[str, Any],
    validation: dict[str, Any],
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if train["return_pct"] <= 0.0:
        failures.append("train_return")
    if validation["return_pct"] <= 0.0:
        failures.append("validation_return")
    if abs(train["max_drawdown_pct"]) > 25.0:
        failures.append("train_mdd")
    if abs(validation["max_drawdown_pct"]) > 25.0:
        failures.append("validation_mdd")
    if train["trades"] < 20:
        failures.append("train_sample")
    if validation["trades"] < 20:
        failures.append("validation_sample")
    if train["profit_factor"] < 1.05:
        failures.append("train_pf")
    if validation["profit_factor"] < 1.05:
        failures.append("validation_pf")
    for name, item in (("train", train), ("validation", validation)):
        if item["top_trade_positive_pnl_share"] > 0.35:
            failures.append(f"{name}_top_trade_concentration")
        if item["top3_trade_positive_pnl_share"] > 0.70:
            failures.append(f"{name}_top3_trade_concentration")
    return not failures, failures


def evaluate(
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    signals: tuple[np.ndarray, np.ndarray],
    config: StrategyConfig,
    end: pd.Timestamp,
    *,
    run_stress: bool = True,
) -> dict[str, Any]:
    long_signal, short_signal = signals
    train = simulate(
        frame,
        funding_path,
        atr,
        long_signal,
        short_signal,
        config,
        TRAIN_START,
        VALIDATION_START,
        label=f"{strategy_id(config)}_train",
    ).metrics
    validation = simulate(
        frame,
        funding_path,
        atr,
        long_signal,
        short_signal,
        config,
        VALIDATION_START,
        DIAGNOSTIC_START,
        label=f"{strategy_id(config)}_validation",
    ).metrics
    passed, failures = development_gate(train, validation)
    stress_train: dict[str, Any] = {}
    stress_validation: dict[str, Any] = {}
    stress_pass = False
    if run_stress:
        stress_config = replace(
            config,
            fee_per_fill=config.fee_per_fill * 2.0,
            slippage_per_fill=config.slippage_per_fill * 2.0,
        )
        stress_train = simulate(
            frame,
            funding_path,
            atr,
            long_signal,
            short_signal,
            stress_config,
            TRAIN_START,
            VALIDATION_START,
            label=f"{strategy_id(config)}_stress_train",
        ).metrics
        stress_validation = simulate(
            frame,
            funding_path,
            atr,
            long_signal,
            short_signal,
            stress_config,
            VALIDATION_START,
            DIAGNOSTIC_START,
            label=f"{strategy_id(config)}_stress_validation",
        ).metrics
        stress_pass = (
            stress_train["return_pct"] > 0.0
            and stress_validation["return_pct"] > 0.0
        )
        if not stress_pass:
            failures.append("double_cost_return")
    return {
        "strategy_id": strategy_id(config),
        "config": asdict(config),
        "train": train,
        "validation": validation,
        "stress_2x_train": stress_train,
        "stress_2x_validation": stress_validation,
        "development_gate": passed,
        "stress_gate": stress_pass,
        "complete_gate": passed and stress_pass,
        "gate_failures": failures,
        "data_end": end.isoformat(),
    }


def rank_key(row: dict[str, Any]) -> tuple[float, float, float]:
    return (
        min(row["train"]["return_pct"], row["validation"]["return_pct"]),
        min(row["train"]["profit_factor"], row["validation"]["profit_factor"]),
        -max(
            abs(row["train"]["max_drawdown_pct"]),
            abs(row["validation"]["max_drawdown_pct"]),
        ),
    )


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {
        "strategy_id": row["strategy_id"],
        "stage": row["stage"],
        "config_json": json.dumps(row["config"], sort_keys=True),
        "development_gate": row["development_gate"],
        "stress_gate": row["stress_gate"],
        "complete_gate": row["complete_gate"],
        "gate_failures": "|".join(row["gate_failures"]),
    }
    for name in (
        "train",
        "validation",
        "stress_2x_train",
        "stress_2x_validation",
        "reused_diagnostic",
        "reused_diagnostic_2x",
        "recent_1y",
    ):
        for key, value in row.get(name, {}).items():
            output[f"{name}_{key}"] = value
    return output


def buy_and_hold(
    frame: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    close = frame.loc[(frame.index >= start) & (frame.index < end), "close"]
    equity = close / float(close.iloc[0])
    drawdown = equity / equity.cummax() - 1.0
    return {
        "return_pct": float((equity.iloc[-1] - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
    }


def rolling_windows(
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    signals: tuple[np.ndarray, np.ndarray],
    config: StrategyConfig,
    end: pd.Timestamp,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cursor = TRAIN_START
    number = 0
    while cursor < end:
        window_end = min(cursor + pd.Timedelta(days=180), end)
        if window_end - cursor < pd.Timedelta(days=60):
            break
        result = simulate(
            frame,
            funding_path,
            atr,
            signals[0],
            signals[1],
            config,
            cursor,
            window_end,
            label=f"rolling_{number:02d}",
        )
        rows.append({"window": number, **result.metrics})
        cursor = window_end
        number += 1
    return pd.DataFrame(rows)


def recent_slices(
    frame: pd.DataFrame,
    funding_path: np.ndarray,
    atr: np.ndarray,
    signals: tuple[np.ndarray, np.ndarray],
    config: StrategyConfig,
    end: pd.Timestamp,
) -> dict[str, Any]:
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    return {
        name: simulate(
            frame,
            funding_path,
            atr,
            signals[0],
            signals[1],
            config,
            max(TRAIN_START, end - delta),
            end,
            label=f"recent_{name}",
        ).metrics
        for name, delta in windows.items()
    }


def main() -> None:
    frame, funding, data_metadata = load_data()
    end = pd.Timestamp(data_metadata["end_exclusive"])
    features = base_features(frame)
    atr = features["atr"].to_numpy(float)
    funding_path = funding_cumulative(frame.index, funding)
    rows: list[dict[str, Any]] = []

    for number, signal_config in enumerate(signal_universe(), start=1):
        signals = build_signals(frame, features, signal_config)
        config = StrategyConfig(
            signal=signal_config,
            stop_atr=4.0,
            max_hold_bars=192,
        )
        row = evaluate(
            frame,
            funding_path,
            atr,
            signals,
            config,
            end,
            run_stress=False,
        )
        row["stage"] = "signal"
        rows.append(row)
        if number % 20 == 0:
            print(f"signal stage {number}/120", flush=True)

    for index, row in enumerate(rows):
        if not row["development_gate"]:
            continue
        config_data = row["config"]
        signal_config = SignalConfig(**config_data["signal"])
        config = StrategyConfig(
            signal=signal_config,
            stop_atr=config_data["stop_atr"],
            max_hold_bars=config_data["max_hold_bars"],
            side_mode=config_data["side_mode"],
            fee_per_fill=config_data["fee_per_fill"],
            slippage_per_fill=config_data["slippage_per_fill"],
        )
        stressed = evaluate(
            frame,
            funding_path,
            atr,
            build_signals(frame, features, signal_config),
            config,
            end,
        )
        stressed["stage"] = "signal"
        rows[index] = stressed

    signal_passes = [row for row in rows if row["complete_gate"]]
    parents = sorted(
        signal_passes if signal_passes else rows,
        key=rank_key,
        reverse=True,
    )[:8]
    for parent in parents:
        signal_config = SignalConfig(**parent["config"]["signal"])
        signals = build_signals(frame, features, signal_config)
        for stop_atr, max_hold_bars in EXIT_PROFILES:
            config = StrategyConfig(
                signal=signal_config,
                stop_atr=stop_atr,
                max_hold_bars=max_hold_bars,
            )
            if strategy_id(config) == parent["strategy_id"]:
                continue
            row = evaluate(frame, funding_path, atr, signals, config, end)
            row["stage"] = "exit"
            rows.append(row)

    complete = [row for row in rows if row["complete_gate"]]
    full_history_robust: list[dict[str, Any]] = []
    for row in complete:
        config_data = row["config"]
        signal_config = SignalConfig(**config_data["signal"])
        config = StrategyConfig(
            signal=signal_config,
            stop_atr=config_data["stop_atr"],
            max_hold_bars=config_data["max_hold_bars"],
            side_mode=config_data["side_mode"],
            fee_per_fill=config_data["fee_per_fill"],
            slippage_per_fill=config_data["slippage_per_fill"],
        )
        signals = build_signals(frame, features, signal_config)
        row["reused_diagnostic"] = simulate(
            frame,
            funding_path,
            atr,
            signals[0],
            signals[1],
            config,
            DIAGNOSTIC_START,
            end,
            label=f"{row['strategy_id']}_diagnostic",
        ).metrics
        row["reused_diagnostic_2x"] = simulate(
            frame,
            funding_path,
            atr,
            signals[0],
            signals[1],
            replace(
                config,
                fee_per_fill=FEE_PER_FILL * 2.0,
                slippage_per_fill=SLIPPAGE_PER_FILL * 2.0,
            ),
            DIAGNOSTIC_START,
            end,
            label=f"{row['strategy_id']}_diagnostic_2x",
        ).metrics
        row["recent_1y"] = simulate(
            frame,
            funding_path,
            atr,
            signals[0],
            signals[1],
            config,
            end - pd.Timedelta(days=365),
            end,
            label=f"{row['strategy_id']}_recent_1y",
        ).metrics
        if (
            row["reused_diagnostic"]["return_pct"] > 0.0
            and row["reused_diagnostic_2x"]["return_pct"] > 0.0
            and row["recent_1y"]["return_pct"] > -5.0
        ):
            full_history_robust.append(row)

    def full_history_key(row: dict[str, Any]) -> tuple[float, float, float]:
        return (
            min(
                row["train"]["return_pct"],
                row["validation"]["return_pct"],
                row["reused_diagnostic"]["return_pct"],
            ),
            min(
                row["stress_2x_train"]["return_pct"],
                row["stress_2x_validation"]["return_pct"],
                row["reused_diagnostic_2x"]["return_pct"],
            ),
            row["recent_1y"]["return_pct"],
        )

    if full_history_robust:
        selected = max(full_history_robust, key=full_history_key)
    elif complete:
        selected = max(complete, key=rank_key)
    else:
        selected = max(rows, key=rank_key)
    selected_config = StrategyConfig(
        signal=SignalConfig(**selected["config"]["signal"]),
        stop_atr=selected["config"]["stop_atr"],
        max_hold_bars=selected["config"]["max_hold_bars"],
        side_mode=selected["config"]["side_mode"],
        fee_per_fill=selected["config"]["fee_per_fill"],
        slippage_per_fill=selected["config"]["slippage_per_fill"],
    )
    selected_signals = build_signals(frame, features, selected_config.signal)

    diagnostic = simulate(
        frame,
        funding_path,
        atr,
        selected_signals[0],
        selected_signals[1],
        selected_config,
        DIAGNOSTIC_START,
        end,
        label="selected_diagnostic",
    )
    diagnostic_stress = simulate(
        frame,
        funding_path,
        atr,
        selected_signals[0],
        selected_signals[1],
        replace(
            selected_config,
            fee_per_fill=FEE_PER_FILL * 2.0,
            slippage_per_fill=SLIPPAGE_PER_FILL * 2.0,
        ),
        DIAGNOSTIC_START,
        end,
        label="selected_diagnostic_2x",
    )
    short_only = simulate(
        frame,
        funding_path,
        atr,
        selected_signals[0],
        selected_signals[1],
        replace(selected_config, side_mode="short"),
        DIAGNOSTIC_START,
        end,
        label="selected_short_only_diagnostic",
    )
    both = simulate(
        frame,
        funding_path,
        atr,
        selected_signals[0],
        selected_signals[1],
        replace(selected_config, side_mode="both"),
        DIAGNOSTIC_START,
        end,
        label="selected_both_diagnostic",
    )
    rolling = rolling_windows(
        frame,
        funding_path,
        atr,
        selected_signals,
        selected_config,
        end,
    )
    atomic_write_csv(WINDOWS_PATH, rolling)
    all_trades = pd.concat(
        [
            simulate(
                frame,
                funding_path,
                atr,
                selected_signals[0],
                selected_signals[1],
                selected_config,
                TRAIN_START,
                VALIDATION_START,
                label="selected_train",
            ).trades,
            simulate(
                frame,
                funding_path,
                atr,
                selected_signals[0],
                selected_signals[1],
                selected_config,
                VALIDATION_START,
                DIAGNOSTIC_START,
                label="selected_validation",
            ).trades,
            diagnostic.trades,
        ],
        ignore_index=True,
    )
    atomic_write_csv(TRADES_PATH, all_trades)
    atomic_write_csv(
        CANDIDATES_PATH,
        pd.DataFrame(
            [
                flatten(row)
                for row in sorted(rows, key=rank_key, reverse=True)
            ]
        ),
    )

    year_metrics: dict[str, Any] = {}
    for year in range(2020, end.year + 1):
        start = pd.Timestamp(year=year, month=1, day=1, tz="UTC")
        year_end = min(
            pd.Timestamp(year=year + 1, month=1, day=1, tz="UTC"),
            end,
        )
        if start >= end:
            continue
        year_metrics[str(year)] = simulate(
            frame,
            funding_path,
            atr,
            selected_signals[0],
            selected_signals[1],
            selected_config,
            start,
            year_end,
            label=f"year_{year}",
        ).metrics

    rolling_positive_ratio = float((rolling["return_pct"] > 0.0).mean())
    yearly_positive_count = sum(
        item["return_pct"] > 0.0 for item in year_metrics.values()
    )
    research_candidate = bool(
        selected["complete_gate"]
        and diagnostic.metrics["return_pct"] > 0.0
        and diagnostic_stress.metrics["return_pct"] > 0.0
        and rolling_positive_ratio > 0.50
        and yearly_positive_count >= 4
        and selected["recent_1y"]["return_pct"] > -5.0
    )
    script_path = Path(__file__).resolve()
    summary = {
        "family": "BTC-15M-Trend-Continuation",
        "research_identity": "BTC-15M-LVCB-LONG-HISTORY-SEARCH-2026-07-20",
        "status": "explore / not promoted / not live-ready",
        "research_role": (
            "full-history research candidate; prospective OOS required"
            if research_candidate
            else "failed diagnostic"
        ),
        "data": data_metadata,
        "splits": {
            "train": [TRAIN_START.isoformat(), VALIDATION_START.isoformat()],
            "validation": [
                VALIDATION_START.isoformat(),
                DIAGNOSTIC_START.isoformat(),
            ],
            "reused_diagnostic": [DIAGNOSTIC_START.isoformat(), end.isoformat()],
            "prospective_oos_start": end.isoformat(),
        },
        "contamination_disclosure": (
            "The mechanism and parameters were explored after viewing full-period "
            "event diagnostics and reused-period probes. No historical segment is "
            "claimed as untouched OOS; only data after prospective_oos_start can "
            "supply fresh evidence."
        ),
        "execution": {
            "entry": "closed 15m signal, next 15m open",
            "stop": "entry-bar active, gap-aware, adverse slippage",
            "time_exit": "max_hold reached at bar open",
            "fee_per_fill": FEE_PER_FILL,
            "adverse_slippage_per_fill": SLIPPAGE_PER_FILL,
            "funding": "official audited historical events",
            "allocation": 1.0,
        },
        "universe": {
            "signal_count": 120,
            "signal_complete_gate_count": len(signal_passes),
            "exit_parent_count": len(parents),
            "total_evaluated": len(rows),
            "complete_gate_count": len(complete),
            "full_history_robust_count": len(full_history_robust),
            "compression_quantiles": COMPRESSION_QUANTILES,
            "compression_lookbacks": COMPRESSION_LOOKBACKS,
            "breakout_windows": BREAKOUT_WINDOWS,
            "ema_pairs": EMA_PAIRS,
            "slope_lags": SLOPE_LAGS,
            "atr_caps": ATR_CAPS,
            "exit_profiles": EXIT_PROFILES,
        },
        "selected": selected,
        "reused_diagnostic": diagnostic.metrics,
        "reused_diagnostic_2x_cost": diagnostic_stress.metrics,
        "direction_ablation": {
            "long_only": diagnostic.metrics,
            "short_only": short_only.metrics,
            "both": both.metrics,
        },
        "year_metrics": year_metrics,
        "rolling_180d": {
            "count": len(rolling),
            "positive_count": int((rolling["return_pct"] > 0.0).sum()),
            "positive_ratio": rolling_positive_ratio,
            "artifact": str(WINDOWS_PATH.relative_to(ROOT)),
        },
        "recent_slices": recent_slices(
            frame,
            funding_path,
            atr,
            selected_signals,
            selected_config,
            end,
        ),
        "benchmarks": {
            "train_buy_hold": buy_and_hold(frame, TRAIN_START, VALIDATION_START),
            "validation_buy_hold": buy_and_hold(
                frame,
                VALIDATION_START,
                DIAGNOSTIC_START,
            ),
            "diagnostic_buy_hold": buy_and_hold(
                frame,
                DIAGNOSTIC_START,
                end,
            ),
        },
        "research_candidate": research_candidate,
        "remaining_blockers": [
            "no untouched historical OOS; prospective evidence begins at frozen end",
            "BTC 1m data absent, so 15m phase gate is incomplete",
            "CPCV and live-executable runner audit not completed",
            "absolute ATR cap requires forward stability monitoring",
        ],
        "provenance": {
            "formula_version": "btc-15m-lvcb-v1-search",
            "source_columns": [
                "ts",
                "open",
                "high",
                "low",
                "close",
                "funding_rate",
            ],
            "generation_time_utc": datetime.now(timezone.utc).isoformat(),
            "code_path": str(script_path.relative_to(ROOT)),
            "code_sha256": sha256_bytes(script_path.read_bytes()),
            "null_policy": "rolling warmup nulls suppress signals",
            "fill_policy": "none",
        },
        "artifacts": {
            "candidates": str(CANDIDATES_PATH.relative_to(ROOT)),
            "trades": str(TRADES_PATH.relative_to(ROOT)),
            "rolling_windows": str(WINDOWS_PATH.relative_to(ROOT)),
        },
    }
    atomic_write_json(SUMMARY_PATH, summary)
    print(json.dumps(finite(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
