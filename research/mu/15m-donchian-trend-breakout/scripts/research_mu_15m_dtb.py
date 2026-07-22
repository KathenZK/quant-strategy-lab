from __future__ import annotations

import argparse
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
FAMILY_DIR = ROOT / "research/mu/15m-donchian-trend-breakout"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
MU_ARTIFACT_DIR = ROOT / "research/mu/artifacts"
DATA_QUALITY_PATH = MU_ARTIFACT_DIR / "mu_binance_15m_data_quality_latest.json"
V14_AUDIT_PATH = MU_ARTIFACT_DIR / "mu_v14_latest_strict_audit.json"

OHLCV_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
FUNDING_ROOT = (
    ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
)
SYMBOL_FILE = "symbol=mu_usdt_usdt.parquet"

DATE = "2026-07-20"
SEARCH_PATH = ARTIFACT_DIR / f"mu_15m_dtb_search_freeze_{DATE}.json"
TRIALS_PATH = ARTIFACT_DIR / f"mu_15m_dtb_search_trials_{DATE}.csv"
REVEAL_PATH = ARTIFACT_DIR / f"mu_15m_dtb_final_audit_{DATE}.json"
TRADES_PATH = ARTIFACT_DIR / f"mu_15m_dtb_final_trades_{DATE}.csv"
EQUITY_PATH = ARTIFACT_DIR / f"mu_15m_dtb_final_equity_{DATE}.csv"

BAR = pd.Timedelta(minutes=15)
TRAIN_START = pd.Timestamp("2026-04-12T00:00:00Z")
TRAIN_END = pd.Timestamp("2026-06-01T00:00:00Z")
VALIDATION_START = pd.Timestamp("2026-06-05T00:00:00Z")
FINAL_START = pd.Timestamp("2026-06-25T00:00:00Z")
FEE_PER_FILL = 0.001
SLIPPAGE_PER_FILL = 0.0004
ENTRY_WINDOWS = (48, 96, 192)
STOP_ATR_VALUES = (3.0, 4.0, 5.0)
REGIME_VALUES = (False, True)
RECENT_WINDOWS: dict[str, pd.Timedelta | None] = {
    "1D": pd.Timedelta(days=1),
    "7D": pd.Timedelta(days=7),
    "1M": pd.Timedelta(days=30),
    "3M": pd.Timedelta(days=90),
    "6M": pd.Timedelta(days=183),
    "1Y": pd.Timedelta(days=365),
    "ALL": None,
}


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    entry_window: int
    stop_atr: float
    use_ema_regime: bool
    allocation: float = 1.0
    fee_per_fill: float = FEE_PER_FILL
    slippage_per_fill: float = SLIPPAGE_PER_FILL

    @property
    def exit_window(self) -> int:
        return self.entry_window // 2


@dataclass(frozen=True, slots=True)
class SimulationResult:
    metrics: dict[str, Any]
    trades: pd.DataFrame
    equity: pd.DataFrame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Frozen low-degree MUUSDT 15m Donchian trend research."
    )
    parser.add_argument("command", choices=("search", "reveal"))
    return parser.parse_args()


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


def payload_sha256(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "payload_sha256"}
    return sha256_bytes(canonical_json_bytes(body))


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


def load_quality() -> dict[str, Any]:
    payload = json.loads(DATA_QUALITY_PATH.read_text(encoding="utf-8"))
    checks = {
        "ohlcv_blockers": payload["ohlcv_quality"]["blocker_count"] == 0,
        "funding_blockers": payload["funding_quality"]["blocker_count"] == 0,
        "contract_trading": payload["contract"]["status"] == "TRADING",
        "contract_type": (
            payload["contract"]["contract_type"] == "TRADIFI_PERPETUAL"
        ),
        "underlying": payload["contract"]["underlying_type"] == "EQUITY",
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"MU data-quality/identity checks failed: {failed}")
    return {
        "path": str(DATA_QUALITY_PATH.relative_to(ROOT)),
        "sha256": sha256_bytes(DATA_QUALITY_PATH.read_bytes()),
        "checks": checks,
    }


def load_market(end_exclusive: pd.Timestamp | None = None) -> pd.DataFrame:
    files = sorted(OHLCV_ROOT.rglob(SYMBOL_FILE))
    if not files:
        raise FileNotFoundError(f"No MU OHLCV under {OHLCV_ROOT}")
    columns = [
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
    frames: list[pd.DataFrame] = []
    partition_mismatch_rows = 0
    for path in files:
        frame = pd.read_parquet(path, columns=columns)
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        expected_date = path.parent.name.removeprefix("date=")
        partition_mismatch_rows += int(
            frame["ts"].dt.date.astype(str).ne(expected_date).sum()
        )
        frames.append(frame)
    market = pd.concat(frames, ignore_index=True)
    if end_exclusive is not None:
        market = market.loc[market["ts"] < end_exclusive].copy()
    market = market.sort_values("ts").reset_index(drop=True)
    expected = pd.date_range(market["ts"].iloc[0], market["ts"].iloc[-1], freq=BAR)
    checks = {
        "partition_dates": partition_mismatch_rows == 0,
        "duplicates": not market["ts"].duplicated().any(),
        "continuity": pd.DatetimeIndex(market["ts"]).equals(expected),
        "closed": bool(market["is_closed"].all()),
        "identity": bool(
            market["exchange"].eq("binance").all()
            and market["symbol"].eq("MU/USDT:USDT").all()
            and market["market_type"].eq("perp").all()
            and market["timeframe"].eq("15m").all()
        ),
        "critical_nulls": not market[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
                "vwap",
                "source",
            ]
        ]
        .isna()
        .any()
        .any(),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"MU market consumer-view checks failed: {failed}")
    return market


def load_funding(end_exclusive: pd.Timestamp | None = None) -> pd.DataFrame:
    files = sorted(FUNDING_ROOT.rglob(SYMBOL_FILE))
    if not files:
        raise FileNotFoundError(f"No MU funding under {FUNDING_ROOT}")
    events = pd.concat(
        [
            pd.read_parquet(
                path,
                columns=[
                    "ts",
                    "exchange",
                    "symbol",
                    "market_type",
                    "funding_rate",
                    "source",
                ],
            )
            for path in files
        ],
        ignore_index=True,
    )
    events["ts"] = pd.to_datetime(events["ts"], utc=True)
    if end_exclusive is not None:
        events = events.loc[events["ts"] < end_exclusive].copy()
    events["funding_rate"] = pd.to_numeric(
        events["funding_rate"], errors="raise"
    ).astype("float64")
    events = events.drop_duplicates(["ts", "funding_rate"]).sort_values("ts")
    if events[["ts", "funding_rate", "source"]].isna().any().any():
        raise RuntimeError("MU funding contains critical nulls")
    if not (
        events["exchange"].eq("binance").all()
        and events["symbol"].eq("MU/USDT:USDT").all()
        and events["market_type"].eq("perp").all()
    ):
        raise RuntimeError("MU funding identity mismatch")
    events["bar_ts"] = events["ts"].dt.floor("15min")
    return (
        events.groupby("bar_ts", as_index=False)["funding_rate"]
        .sum()
        .rename(columns={"bar_ts": "ts"})
        .sort_values("ts")
        .reset_index(drop=True)
    )


def load_data(
    end_exclusive: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    quality = load_quality()
    market = load_market(end_exclusive)
    funding = load_funding(end_exclusive)
    funding_by_bar = funding.set_index("ts")["funding_rate"]
    market["funding_rate"] = (
        funding_by_bar.reindex(pd.DatetimeIndex(market["ts"])).fillna(0.0).to_numpy()
    )
    metadata = {
        "quality": quality,
        "market_rows": int(len(market)),
        "funding_bars": int(len(funding)),
        "start": market["ts"].iloc[0].isoformat(),
        "end": market["ts"].iloc[-1].isoformat(),
        "end_exclusive_requested": (
            end_exclusive.isoformat() if end_exclusive is not None else None
        ),
        "market_fingerprint": sha256_bytes(
            pd.util.hash_pandas_object(
                market[["ts", "open", "high", "low", "close", "volume"]],
                index=False,
            ).values.tobytes()
        ),
    }
    return market, metadata


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    features = frame.copy()
    close = features["close"]
    features["ema96"] = close.ewm(
        span=96, adjust=False, min_periods=96
    ).mean()
    features["ema384"] = close.ewm(
        span=384, adjust=False, min_periods=384
    ).mean()
    features["ema384_slope16"] = features["ema384"].pct_change(16)
    features["atr96"] = true_range(features).rolling(
        96, min_periods=96
    ).mean()
    for window in ENTRY_WINDOWS:
        features[f"donchian_high_{window}"] = (
            features["high"].rolling(window, min_periods=window).max().shift(1)
        )
        exit_window = window // 2
        features[f"donchian_low_{exit_window}"] = (
            features["low"]
            .rolling(exit_window, min_periods=exit_window)
            .min()
            .shift(1)
        )
    return features


def build_signals(
    features: pd.DataFrame,
    config: StrategyConfig,
) -> tuple[np.ndarray, np.ndarray]:
    regime = (
        features["ema96"].gt(features["ema384"])
        & features["ema384_slope16"].gt(0.0)
    )
    if not config.use_ema_regime:
        regime = pd.Series(True, index=features.index)
    entry = (
        regime
        & features["close"].gt(features[f"donchian_high_{config.entry_window}"])
        & features["atr96"].gt(0.0)
    )
    channel_exit = features["close"].lt(
        features[f"donchian_low_{config.exit_window}"]
    )
    if config.use_ema_regime:
        channel_exit = channel_exit | ~regime
    return (
        entry.fillna(False).to_numpy(dtype=bool),
        channel_exit.fillna(False).to_numpy(dtype=bool),
    )


def simulate(
    features: pd.DataFrame,
    config: StrategyConfig,
    *,
    start: pd.Timestamp,
    end_exclusive: pd.Timestamp,
    liquidate_at_end: bool = True,
) -> SimulationResult:
    active = features.loc[
        (features["ts"] >= start) & (features["ts"] < end_exclusive)
    ].copy()
    if len(active) < 2:
        raise ValueError(f"Insufficient bars for {start} -> {end_exclusive}")
    entry_signal, exit_signal = build_signals(features, config)
    source_positions = features.index[
        (features["ts"] >= start) & (features["ts"] < end_exclusive)
    ].to_numpy()

    open_ = features["open"].to_numpy(dtype="float64")
    high = features["high"].to_numpy(dtype="float64")
    low = features["low"].to_numpy(dtype="float64")
    close = features["close"].to_numpy(dtype="float64")
    atr = features["atr96"].to_numpy(dtype="float64")
    funding = features["funding_rate"].to_numpy(dtype="float64")
    ts = pd.to_datetime(features["ts"], utc=True)

    equity = 1.0
    position = False
    pending_entry = False
    pending_exit = False
    entry_i = -1
    entry_fill = np.nan
    entry_equity = np.nan
    stop = np.nan
    last_mark = np.nan
    peak_high = np.nan
    trades: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []
    gap_stops = 0
    exit_stop_conflicts = 0

    def close_position(i: int, raw_fill: float, reason: str) -> None:
        nonlocal equity, position, pending_entry, pending_exit
        nonlocal entry_i, entry_fill, entry_equity, stop, last_mark, peak_high
        fill = raw_fill * (1.0 - config.slippage_per_fill)
        equity *= 1.0 + config.allocation * (fill / last_mark - 1.0)
        equity *= 1.0 - config.fee_per_fill * config.allocation
        trade_return = equity / entry_equity - 1.0
        trades.append(
            {
                "entry_ts": ts.iloc[entry_i].isoformat(),
                "exit_ts": ts.iloc[i].isoformat(),
                "entry_fill": float(entry_fill),
                "exit_fill": float(fill),
                "stop_at_exit": float(stop),
                "bars_held": int(i - entry_i + 1),
                "exit_reason": reason,
                "trade_return": float(trade_return),
                "equity_after": float(equity),
            }
        )
        position = False
        pending_entry = False
        pending_exit = False
        entry_i = -1
        entry_fill = np.nan
        entry_equity = np.nan
        stop = np.nan
        last_mark = np.nan
        peak_high = np.nan

    for i in source_positions:
        exited_this_bar = False
        if position:
            equity *= 1.0 + config.allocation * (open_[i] / last_mark - 1.0)
            last_mark = open_[i]
            equity *= 1.0 - config.allocation * funding[i]
            if pending_exit:
                close_position(i, open_[i], "channel_or_regime_exit")
                exited_this_bar = True

        if pending_entry and not position and not exited_this_bar:
            pending_entry = False
            signal_i = i - 1
            if signal_i >= 0 and np.isfinite(atr[signal_i]) and atr[signal_i] > 0.0:
                position = True
                entry_i = i
                entry_fill = open_[i] * (1.0 + config.slippage_per_fill)
                entry_equity = equity
                equity *= 1.0 - config.fee_per_fill * config.allocation
                last_mark = entry_fill
                peak_high = high[i]
                stop = entry_fill - config.stop_atr * atr[signal_i]

        if position:
            if open_[i] <= stop:
                gap_stops += 1
                close_position(i, open_[i], "stop_gap")
                exited_this_bar = True
            elif low[i] <= stop:
                if exit_signal[i]:
                    exit_stop_conflicts += 1
                close_position(i, stop, "stop")
                exited_this_bar = True

        if position:
            equity *= 1.0 + config.allocation * (close[i] / last_mark - 1.0)
            last_mark = close[i]
            peak_high = max(float(peak_high), float(high[i]))
            if np.isfinite(atr[i]) and atr[i] > 0.0:
                stop = max(float(stop), peak_high - config.stop_atr * atr[i])
            if exit_signal[i]:
                pending_exit = True

        if not position and not exited_this_bar and entry_signal[i]:
            pending_entry = True

        if not np.isfinite(equity) or equity <= 0.0:
            raise RuntimeError(
                f"Non-positive/non-finite equity at {ts.iloc[i].isoformat()}"
            )
        curve.append(
            {
                "ts": ts.iloc[i],
                "equity": float(equity),
                "position": int(position),
            }
        )

    if position and liquidate_at_end:
        final_i = int(source_positions[-1])
        close_position(final_i, close[final_i], "segment_end")
        curve[-1]["equity"] = float(equity)
        curve[-1]["position"] = 0

    equity_frame = pd.DataFrame(curve)
    equity_series = equity_frame.set_index("ts")["equity"]
    drawdown = equity_series / equity_series.cummax() - 1.0
    trade_frame = pd.DataFrame(trades)
    trade_returns = (
        trade_frame["trade_return"].to_numpy(dtype="float64")
        if not trade_frame.empty
        else np.array([], dtype="float64")
    )
    gains = float(trade_returns[trade_returns > 0.0].sum())
    losses = float(-trade_returns[trade_returns < 0.0].sum())
    profit_factor = gains / losses if losses > 0.0 else (math.inf if gains > 0 else 0.0)
    metrics = {
        "start": start.isoformat(),
        "end_exclusive": end_exclusive.isoformat(),
        "bars": int(len(equity_frame)),
        "return": float(equity_series.iloc[-1] - 1.0),
        "max_drawdown": float(drawdown.min()),
        "closed_trades": int(len(trade_frame)),
        "win_rate": (
            float((trade_returns > 0.0).mean()) if len(trade_returns) else 0.0
        ),
        "profit_factor": profit_factor,
        "exposure": float(equity_frame["position"].mean()),
        "minimum_equity": float(equity_series.min()),
        "gap_stops": gap_stops,
        "exit_stop_conflicts": exit_stop_conflicts,
        "open_position_at_end": bool(position and not liquidate_at_end),
        "exit_reasons": (
            trade_frame["exit_reason"].value_counts().to_dict()
            if not trade_frame.empty
            else {}
        ),
    }
    return SimulationResult(metrics=metrics, trades=trade_frame, equity=equity_frame)


def buy_hold(
    features: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end_exclusive: pd.Timestamp,
) -> dict[str, Any]:
    active = features.loc[
        (features["ts"] >= start) & (features["ts"] < end_exclusive)
    ].copy()
    entry_fill = float(active["open"].iloc[0]) * (1.0 + SLIPPAGE_PER_FILL)
    equity = 1.0 - FEE_PER_FILL
    last_mark = entry_fill
    curve: list[float] = []
    for row in active.itertuples(index=False):
        equity *= float(row.open) / last_mark
        last_mark = float(row.open)
        equity *= 1.0 - float(row.funding_rate)
        equity *= float(row.close) / last_mark
        last_mark = float(row.close)
        curve.append(equity)
    exit_fill = float(active["close"].iloc[-1]) * (1.0 - SLIPPAGE_PER_FILL)
    equity *= exit_fill / last_mark
    equity *= 1.0 - FEE_PER_FILL
    curve[-1] = equity
    series = pd.Series(curve)
    drawdown = series / series.cummax() - 1.0
    return {
        "return": float(equity - 1.0),
        "max_drawdown": float(drawdown.min()),
    }


def strategy_id(config: StrategyConfig) -> str:
    identity = {
        "family": "MU-15M-DTB",
        "entry_window": config.entry_window,
        "exit_window": config.exit_window,
        "stop_atr": config.stop_atr,
        "use_ema_regime": config.use_ema_regime,
        "allocation": config.allocation,
        "fee_per_fill": config.fee_per_fill,
        "slippage_per_fill": config.slippage_per_fill,
    }
    return f"dtb-{sha256_bytes(canonical_json_bytes(identity))[:12]}"


def config_universe() -> list[StrategyConfig]:
    return [
        StrategyConfig(
            entry_window=entry_window,
            stop_atr=stop_atr,
            use_ema_regime=use_ema_regime,
        )
        for entry_window, stop_atr, use_ema_regime in product(
            ENTRY_WINDOWS,
            STOP_ATR_VALUES,
            REGIME_VALUES,
        )
    ]


def compact(metrics: dict[str, Any], prefix: str) -> dict[str, Any]:
    return {
        f"{prefix}_return": metrics["return"],
        f"{prefix}_max_drawdown": metrics["max_drawdown"],
        f"{prefix}_trades": metrics["closed_trades"],
        f"{prefix}_win_rate": metrics["win_rate"],
        f"{prefix}_profit_factor": metrics["profit_factor"],
    }


def evaluate_candidate(
    features: pd.DataFrame,
    config: StrategyConfig,
) -> dict[str, Any]:
    train = simulate(
        features,
        config,
        start=TRAIN_START,
        end_exclusive=TRAIN_END,
    ).metrics
    validation = simulate(
        features,
        config,
        start=VALIDATION_START,
        end_exclusive=FINAL_START,
    ).metrics
    stressed = replace(
        config,
        fee_per_fill=2.0 * FEE_PER_FILL,
        slippage_per_fill=2.0 * SLIPPAGE_PER_FILL,
    )
    stress_train = simulate(
        features,
        stressed,
        start=TRAIN_START,
        end_exclusive=TRAIN_END,
    ).metrics
    stress_validation = simulate(
        features,
        stressed,
        start=VALIDATION_START,
        end_exclusive=FINAL_START,
    ).metrics
    row = {
        "strategy_id": strategy_id(config),
        **asdict(config),
        "exit_window": config.exit_window,
        **compact(train, "train"),
        **compact(validation, "validation"),
        "stress_train_return": stress_train["return"],
        "stress_validation_return": stress_validation["return"],
    }
    row["base_gate"] = bool(
        train["return"] > 0.0
        and train["closed_trades"] >= 8
        and train["max_drawdown"] >= -0.25
        and train["profit_factor"] >= 1.10
        and validation["return"] > 0.0
        and validation["closed_trades"] >= 5
        and validation["max_drawdown"] >= -0.25
        and validation["profit_factor"] >= 1.00
        and stress_train["return"] > 0.0
        and stress_validation["return"] > 0.0
    )
    row["conservative_score"] = min(train["return"], validation["return"])
    return row


def add_neighborhood(rows: list[dict[str, Any]]) -> None:
    entry_position = {value: index for index, value in enumerate(ENTRY_WINDOWS)}
    stop_position = {value: index for index, value in enumerate(STOP_ATR_VALUES)}
    for row in rows:
        neighbors = [
            candidate
            for candidate in rows
            if candidate["use_ema_regime"] == row["use_ema_regime"]
            and abs(
                entry_position[candidate["entry_window"]]
                - entry_position[row["entry_window"]]
            )
            + abs(
                stop_position[candidate["stop_atr"]]
                - stop_position[row["stop_atr"]]
            )
            <= 1
        ]
        positive = [
            candidate
            for candidate in neighbors
            if candidate["train_return"] > 0.0
            and candidate["validation_return"] > 0.0
        ]
        row["neighborhood_size"] = len(neighbors)
        row["neighborhood_joint_positive"] = len(positive)
        row["neighborhood_positive_ratio"] = (
            len(positive) / len(neighbors) if neighbors else 0.0
        )
        row["candidate_gate"] = bool(
            row["base_gate"] and row["neighborhood_positive_ratio"] >= 0.5
        )


def prefix_causality_audit(
    market: pd.DataFrame,
    full_features: pd.DataFrame,
) -> dict[str, Any]:
    checkpoints = [
        int(len(market) * fraction)
        for fraction in (0.55, 0.75, 0.9)
        if int(len(market) * fraction) > 400
    ]
    columns = [
        "ema96",
        "ema384",
        "ema384_slope16",
        "atr96",
        "donchian_high_96",
        "donchian_low_48",
    ]
    mismatches: list[dict[str, Any]] = []
    for index in checkpoints:
        prefix = build_features(market.iloc[: index + 1].copy())
        for column in columns:
            full_value = full_features[column].iloc[index]
            prefix_value = prefix[column].iloc[-1]
            if not np.isclose(
                float(full_value),
                float(prefix_value),
                rtol=0.0,
                atol=1e-12,
                equal_nan=True,
            ):
                mismatches.append(
                    {
                        "ts": market["ts"].iloc[index].isoformat(),
                        "column": column,
                        "full": float(full_value),
                        "prefix": float(prefix_value),
                    }
                )
    return {
        "checkpoints": [market["ts"].iloc[index].isoformat() for index in checkpoints],
        "columns": columns,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "pass": not mismatches,
    }


def search() -> None:
    if SEARCH_PATH.exists() or TRIALS_PATH.exists():
        raise RuntimeError("Frozen search artifacts already exist; refusing overwrite")
    market, metadata = load_data(FINAL_START)
    if pd.Timestamp(market["ts"].iloc[-1]) >= FINAL_START:
        raise RuntimeError("Search view leaked final-audit bars")
    features = build_features(market)
    rows = [evaluate_candidate(features, config) for config in config_universe()]
    if len(rows) != 18:
        raise RuntimeError(f"Expected exactly 18 trials, got {len(rows)}")
    add_neighborhood(rows)
    eligible = [row for row in rows if row["candidate_gate"]]
    selected = (
        max(eligible, key=lambda row: (row["conservative_score"], row["strategy_id"]))
        if eligible
        else None
    )
    trials = pd.DataFrame(rows).sort_values(
        ["candidate_gate", "conservative_score", "strategy_id"],
        ascending=[False, False, True],
    )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "MU-15M-Donchian-Trend-Breakout",
        "status": "explore / not promoted / not live-ready",
        "protocol": {
            "train": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
            "gap": [TRAIN_END.isoformat(), VALIDATION_START.isoformat()],
            "validation": [VALIDATION_START.isoformat(), FINAL_START.isoformat()],
            "final_audit_sealed_from": FINAL_START.isoformat(),
            "trial_count": len(rows),
            "selection_rule": (
                "base gate + same-regime Manhattan-neighborhood joint-positive "
                "ratio >= 0.5; maximize min(train_return, validation_return)"
            ),
        },
        "data": metadata,
        "execution": {
            "entry": "closed 15m breakout, next 15m open",
            "exit": "channel/regime close decision, next 15m open",
            "stop": "entry-bar active; gap-aware; trailing updates after close",
            "fee_per_fill": FEE_PER_FILL,
            "adverse_slippage_per_fill": SLIPPAGE_PER_FILL,
            "funding": "actual Binance events; same-bar events summed",
            "allocation": 1.0,
        },
        "universe": {
            "entry_windows": list(ENTRY_WINDOWS),
            "exit_rule": "entry_window // 2",
            "stop_atr": list(STOP_ATR_VALUES),
            "ema_regime": list(REGIME_VALUES),
        },
        "trials_sha256": sha256_bytes(
            trials.to_csv(index=False).encode("utf-8")
        ),
        "eligible_count": len(eligible),
        "selected": selected,
        "verdict": "candidate_frozen" if selected else "no_candidate",
        "code": {
            "path": str(Path(__file__).resolve().relative_to(ROOT)),
            "sha256": sha256_bytes(Path(__file__).read_bytes()),
        },
    }
    atomic_write_csv(TRIALS_PATH, trials)
    atomic_write_json(SEARCH_PATH, payload)
    print(
        json.dumps(
            {
                "trials": len(rows),
                "eligible": len(eligible),
                "selected": selected["strategy_id"] if selected else None,
                "freeze": str(SEARCH_PATH.relative_to(ROOT)),
            },
            indent=2,
        )
    )


def load_freeze() -> dict[str, Any]:
    payload = json.loads(SEARCH_PATH.read_text(encoding="utf-8"))
    expected = payload.pop("payload_sha256")
    actual = payload_sha256(payload)
    if actual != expected:
        raise RuntimeError(f"Search freeze hash mismatch: {expected} != {actual}")
    payload["payload_sha256"] = expected
    if payload["protocol"]["final_audit_sealed_from"] != FINAL_START.isoformat():
        raise RuntimeError("Final-audit boundary drift")
    return payload


def recent_slices(
    features: pd.DataFrame,
    config: StrategyConfig,
    data_end_exclusive: pd.Timestamp,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    earliest = pd.Timestamp(features["ts"].iloc[0])
    for label, delta in RECENT_WINDOWS.items():
        requested_start = TRAIN_START if delta is None else data_end_exclusive - delta
        start = max(TRAIN_START, requested_start, earliest)
        result = simulate(
            features,
            config,
            start=start,
            end_exclusive=data_end_exclusive,
        )
        benchmark = buy_hold(
            features,
            start=start,
            end_exclusive=data_end_exclusive,
        )
        results[label] = {
            **result.metrics,
            "coverage_complete": bool(delta is None or start <= requested_start),
            "buy_hold": benchmark,
            "excess_return_vs_buy_hold": (
                result.metrics["return"] - benchmark["return"]
            ),
        }
    return results


def reveal() -> None:
    if REVEAL_PATH.exists():
        raise RuntimeError("Final audit was already revealed; refusing overwrite")
    freeze = load_freeze()
    selected = freeze.get("selected")
    if selected is None:
        payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "family": "MU-15M-Donchian-Trend-Breakout",
            "status": "explore / not promoted / not live-ready",
            "search_freeze": str(SEARCH_PATH.relative_to(ROOT)),
            "search_freeze_sha256": sha256_bytes(SEARCH_PATH.read_bytes()),
            "verdict": "no_candidate",
            "reason": "No train/validation candidate passed the frozen gate; final audit remained unused.",
        }
        atomic_write_json(REVEAL_PATH, payload)
        print(json.dumps(payload, indent=2))
        return

    market, metadata = load_data()
    data_end_exclusive = pd.Timestamp(market["ts"].iloc[-1]) + BAR
    features = build_features(market)
    config = StrategyConfig(
        entry_window=int(selected["entry_window"]),
        stop_atr=float(selected["stop_atr"]),
        use_ema_regime=bool(selected["use_ema_regime"]),
    )
    if strategy_id(config) != selected["strategy_id"]:
        raise RuntimeError("Frozen strategy identity drift")

    causal = prefix_causality_audit(market, features)
    if not causal["pass"]:
        raise RuntimeError(f"Feature causality audit failed: {causal}")
    final = simulate(
        features,
        config,
        start=FINAL_START,
        end_exclusive=data_end_exclusive,
    )
    final_stress = simulate(
        features,
        replace(
            config,
            fee_per_fill=2.0 * FEE_PER_FILL,
            slippage_per_fill=2.0 * SLIPPAGE_PER_FILL,
        ),
        start=FINAL_START,
        end_exclusive=data_end_exclusive,
    )
    final_benchmark = buy_hold(
        features,
        start=FINAL_START,
        end_exclusive=data_end_exclusive,
    )
    audit_pass = bool(
        final.metrics["return"] > 0.0
        and final.metrics["closed_trades"] >= 8
        and final.metrics["return"] >= final_benchmark["return"]
        and final.metrics["max_drawdown"] >= -0.25
        and final_stress.metrics["return"] > 0.0
    )
    if final.metrics["closed_trades"] < 8:
        verdict = "sample_insufficient"
    elif audit_pass:
        verdict = "found_explore_candidate"
    else:
        verdict = "failed_final_audit"

    slices = recent_slices(features, config, data_end_exclusive)
    all_result = simulate(
        features,
        config,
        start=TRAIN_START,
        end_exclusive=data_end_exclusive,
    )
    turtle_config = StrategyConfig(
        entry_window=96,
        stop_atr=4.0,
        use_ema_regime=False,
    )
    turtle = simulate(
        features,
        turtle_config,
        start=FINAL_START,
        end_exclusive=data_end_exclusive,
    )
    v14 = (
        json.loads(V14_AUDIT_PATH.read_text(encoding="utf-8"))
        if V14_AUDIT_PATH.exists()
        else None
    )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "MU-15M-Donchian-Trend-Breakout",
        "status": "explore / not promoted / not live-ready",
        "search_freeze": {
            "path": str(SEARCH_PATH.relative_to(ROOT)),
            "sha256": sha256_bytes(SEARCH_PATH.read_bytes()),
            "payload_sha256": freeze["payload_sha256"],
        },
        "selected": selected,
        "config_reconstructed": asdict(config),
        "data": metadata,
        "causality_audit": causal,
        "final_audit": {
            **final.metrics,
            "benchmark": final_benchmark,
            "excess_return_vs_buy_hold": (
                final.metrics["return"] - final_benchmark["return"]
            ),
            "double_cost_return": final_stress.metrics["return"],
            "gate_pass": audit_pass,
        },
        "all_since_train_start": all_result.metrics,
        "recent_slices": slices,
        "fixed_turtle_final_audit": {
            "config": asdict(turtle_config),
            "metrics": turtle.metrics,
        },
        "v14_strict_comparison": (
            {
                "all": v14["windows"]["ALL"],
                "new_data_forward_extension": v14[
                    "new_data_forward_extension_strict"
                ],
            }
            if v14
            else None
        ),
        "verdict": verdict,
        "limitations": [
            "Final audit is a one-time retrospective holdout, not future prospective evidence.",
            "Binance MUUSDT history is shorter than 6 months.",
            "Passing this audit cannot satisfy repository CPCV/MC/phase/promotion gates.",
        ],
    }
    final_trades = final.trades.copy()
    final_trades["segment"] = "final_audit"
    all_trades = all_result.trades.copy()
    all_trades["segment"] = "all_since_train_start"
    atomic_write_csv(
        TRADES_PATH,
        pd.concat([final_trades, all_trades], ignore_index=True),
    )
    final_equity = final.equity.copy()
    final_equity["segment"] = "final_audit"
    all_equity = all_result.equity.copy()
    all_equity["segment"] = "all_since_train_start"
    atomic_write_csv(
        EQUITY_PATH,
        pd.concat([final_equity, all_equity], ignore_index=True),
    )
    atomic_write_json(REVEAL_PATH, payload)
    print(
        json.dumps(
            {
                "selected": selected["strategy_id"],
                "final_return": final.metrics["return"],
                "final_trades": final.metrics["closed_trades"],
                "verdict": verdict,
                "artifact": str(REVEAL_PATH.relative_to(ROOT)),
            },
            indent=2,
        )
    )


def main() -> None:
    args = parse_args()
    if args.command == "search":
        search()
    else:
        reveal()


if __name__ == "__main__":
    main()
