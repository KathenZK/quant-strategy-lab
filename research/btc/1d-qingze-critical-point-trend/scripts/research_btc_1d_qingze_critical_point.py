from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/1d-qingze-critical-point-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NORMALIZED_ROOT = (
    ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1h"
)
RAW_ROOT = (
    ROOT / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=1h"
)
FUNDING_PATH = (
    ROOT
    / "data/normalized/funding/exchange=binance/market_type=perp"
    / "symbol=btc_usdt_usdt/funding.parquet"
)
OI_ROOT = (
    ROOT
    / "data/normalized/open_interest/exchange=binance/market_type=perp"
    / "timeframe=15m"
)

SYMBOL = "BTCUSDT"
SYMBOL_SLUG = "btc_usdt_usdt"
FEE_PER_FILL = 0.001
SLIPPAGE_PER_FILL = 0.0004
ATR_LOOKBACK = 14
BREAKOUT_LOOKBACK = 20
NARROW_LOOKBACK = 5
VOLUME_MULTIPLIER = 1.5
DEVIATION_MIN = 0.015
IMPULSE_MIN = 0.02
NARROW_RANGE_MAX = 0.015
STOP_ATR = 3.0
TRANCHE_WEIGHTS = (0.20, 0.12, 0.08)
ADD_ATR_LEVELS = (1.0, 2.0)


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    ma_days: int
    use_a: bool
    use_b: bool
    pyramiding: bool = True


VARIANTS = (
    Variant("sma60_a_b_pyramid", 60, True, True, True),
    Variant("sma60_a_only_pyramid", 60, True, False, True),
    Variant("sma60_b_only_pyramid", 60, False, True, True),
    Variant("sma60_a_b_initial_only", 60, True, True, False),
    Variant("sma55_a_b_pyramid", 55, True, True, True),
)
BASE_VARIANT = VARIANTS[0].name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BTC 1D Qingze trend plus critical-point diagnostic backtest."
    )
    parser.add_argument(
        "--run-date", default=datetime.now(UTC).date().isoformat()
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def partition_paths(root: Path, slug: str) -> list[Path]:
    paths = sorted(root.glob(f"date=*/symbol={slug}.parquet"))
    if not paths:
        raise FileNotFoundError(f"no partitions for {slug} under {root}")
    return paths


def load_partitions(paths: list[Path]) -> pd.DataFrame:
    return pd.concat(
        [pd.read_parquet(path) for path in paths], ignore_index=True
    )


def load_and_audit() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    normalized = load_partitions(partition_paths(NORMALIZED_ROOT, SYMBOL_SLUG))
    raw = load_partitions(partition_paths(RAW_ROOT, SYMBOL_SLUG))
    funding = pd.read_parquet(FUNDING_PATH)

    normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True)
    raw["open_time"] = pd.to_datetime(raw["open_time"], utc=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding["funding_rate"] = pd.to_numeric(
        funding["funding_rate"], errors="coerce"
    )
    normalized = normalized.sort_values("ts").reset_index(drop=True)
    raw = raw.sort_values("open_time").reset_index(drop=True)
    funding = funding.sort_values("ts").reset_index(drop=True)

    accepted_start = funding["ts"].iloc[0].ceil("D")
    normalized = normalized.loc[
        normalized["ts"].ge(accepted_start)
    ].reset_index(drop=True)
    raw = raw.loc[raw["open_time"].ge(accepted_start)].reset_index(drop=True)

    required = [
        "ts",
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
    missing_columns = sorted(set(required).difference(normalized.columns))
    expected = pd.date_range(
        normalized["ts"].iloc[0], normalized["ts"].iloc[-1], freq="1h"
    )
    missing_timestamps = expected.difference(
        pd.DatetimeIndex(normalized["ts"])
    )
    critical_nulls = {
        column: int(normalized[column].isna().sum())
        for column in required
        if column in normalized
    }
    invalid_ohlc = int(
        (
            (normalized[["open", "high", "low", "close"]] <= 0.0).any(axis=1)
            | normalized["high"].lt(
                normalized[["open", "close", "low"]].max(axis=1)
            )
            | normalized["low"].gt(
                normalized[["open", "close", "high"]].min(axis=1)
            )
        ).sum()
    )
    compare = normalized[
        [
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "trade_count",
        ]
    ].merge(
        raw[
            [
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
            ]
        ],
        left_on="ts",
        right_on="open_time",
        how="outer",
        suffixes=("_normalized", "_raw"),
        indicator=True,
    )
    both = compare.loc[compare["_merge"].eq("both")]
    mismatch: dict[str, int] = {}
    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
    ):
        left = pd.to_numeric(
            both[f"{column}_normalized"], errors="coerce"
        ).to_numpy("float64")
        right = pd.to_numeric(
            both[f"{column}_raw"], errors="coerce"
        ).to_numpy("float64")
        mismatch[column] = int(
            (
                ~np.isclose(
                    left,
                    right,
                    rtol=0.0,
                    atol=0.0 if column == "trade_count" else 1e-12,
                )
            ).sum()
        )
    expected_vwap = normalized["quote_volume"].div(
        normalized["volume"].replace(0.0, np.nan)
    )
    vwap_formula_mismatch = int(
        (
            ~np.isclose(
                normalized["vwap"].to_numpy("float64"),
                expected_vwap.to_numpy("float64"),
                rtol=1e-12,
                atol=1e-12,
                equal_nan=True,
            )
        ).sum()
    )

    funding_gaps = funding["ts"].diff().dropna()
    funding_quality = {
        "rows": int(len(funding)),
        "first_ts": funding["ts"].iloc[0].isoformat(),
        "last_ts": funding["ts"].iloc[-1].isoformat(),
        "duplicate_ts": int(funding["ts"].duplicated().sum()),
        "critical_null_rows": int(
            funding[["ts", "funding_rate"]].isna().any(axis=1).sum()
        ),
        "max_gap_hours": float(
            funding_gaps.max().total_seconds() / 3600.0
        ),
    }
    funding_quality["blocker_count"] = int(
        funding_quality["duplicate_ts"]
        + funding_quality["critical_null_rows"]
        + (funding_quality["max_gap_hours"] > 8.01)
    )
    blocker_count = int(
        len(missing_columns)
        + len(missing_timestamps)
        + normalized["ts"].duplicated().sum()
        + raw["open_time"].duplicated().sum()
        + sum(critical_nulls.values())
        + invalid_ohlc
        + (~normalized["is_closed"].astype(bool)).sum()
        + compare["_merge"].ne("both").sum()
        + sum(mismatch.values())
        + vwap_formula_mismatch
        + funding_quality["blocker_count"]
    )
    quality = {
        "symbol": SYMBOL,
        "exchange": "Binance",
        "market_type": "USD-M perpetual",
        "source_timeframe": "1h",
        "research_timeframe": "UTC 1d",
        "accepted_start_reason": (
            "first complete UTC day after normalized funding coverage begins"
        ),
        "hourly_rows": int(len(normalized)),
        "first_hour": normalized["ts"].iloc[0].isoformat(),
        "last_hour": normalized["ts"].iloc[-1].isoformat(),
        "expected_hourly_rows": int(len(expected)),
        "missing_hourly_bars": int(len(missing_timestamps)),
        "duplicate_normalized": int(normalized["ts"].duplicated().sum()),
        "duplicate_raw": int(raw["open_time"].duplicated().sum()),
        "critical_nulls": critical_nulls,
        "invalid_ohlc_rows": invalid_ohlc,
        "non_closed_rows": int(
            (~normalized["is_closed"].astype(bool)).sum()
        ),
        "raw_normalized_unmatched_rows": int(
            compare["_merge"].ne("both").sum()
        ),
        "raw_normalized_mismatch": mismatch,
        "vwap_formula_mismatch": vwap_formula_mismatch,
        "source_values": sorted(
            normalized["source"].dropna().astype(str).unique().tolist()
        ),
        "funding": funding_quality,
        "blocker_count": blocker_count,
    }
    if blocker_count:
        raise RuntimeError(f"data-quality blockers: {quality}")
    return normalized, funding[["ts", "funding_rate"]].copy(), quality


def aggregate_daily(
    hourly: pd.DataFrame, funding: pd.DataFrame
) -> pd.DataFrame:
    frame = hourly[
        [
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "trade_count",
        ]
    ].copy()
    frame["day"] = frame["ts"].dt.floor("D")
    rows: list[dict[str, Any]] = []
    for day, group in frame.groupby("day", sort=True):
        group = group.sort_values("ts")
        expected = pd.date_range(pd.Timestamp(day), periods=24, freq="1h")
        if len(group) != 24 or not pd.DatetimeIndex(group["ts"]).equals(
            expected
        ):
            continue
        rows.append(
            {
                "ts": expected[0],
                "open": float(group["open"].iloc[0]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group["close"].iloc[-1]),
                "volume": float(group["volume"].sum()),
                "quote_volume": float(group["quote_volume"].sum()),
                "trade_count": int(group["trade_count"].sum()),
            }
        )
    daily = pd.DataFrame(rows)
    if daily.empty:
        raise RuntimeError("no complete UTC daily bars")
    daily["ts"] = pd.to_datetime(daily["ts"], utc=True)

    rates = funding.copy()
    rates["day"] = rates["ts"].dt.floor("D")
    daily_funding = rates.groupby("day", as_index=False).agg(
        funding_rate_sum=("funding_rate", "sum"),
        funding_events=("funding_rate", "size"),
    )
    daily = daily.merge(
        daily_funding, left_on="ts", right_on="day", how="left"
    ).drop(columns="day")
    daily["funding_rate_sum"] = daily["funding_rate_sum"].fillna(0.0)
    daily["funding_events"] = daily["funding_events"].fillna(0).astype(int)
    return daily


def add_features(daily: pd.DataFrame, ma_days: int) -> pd.DataFrame:
    data = daily.copy()
    previous_close = data["close"].shift(1)
    true_range = pd.concat(
        [
            data["high"] - data["low"],
            (data["high"] - previous_close).abs(),
            (data["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["atr"] = true_range.rolling(ATR_LOOKBACK).mean()
    data["sma"] = data["close"].rolling(ma_days).mean()
    data["sma_slope"] = data["sma"].diff()
    data["deviation"] = data["close"] / data["sma"] - 1.0
    data["return_1d"] = data["close"].pct_change()
    above = data["close"].gt(data["sma"])
    below = data["close"].lt(data["sma"])
    above_three = above.rolling(3).sum().eq(3)
    below_three = below.rolling(3).sum().eq(3)
    data["trend"] = np.select(
        [
            above_three
            & data["deviation"].ge(DEVIATION_MIN)
            & data["sma_slope"].gt(0),
            below_three
            & data["deviation"].le(-DEVIATION_MIN)
            & data["sma_slope"].lt(0),
        ],
        [1, -1],
        default=0,
    ).astype(int)
    data["prior20_high"] = (
        data["high"].shift(1).rolling(BREAKOUT_LOOKBACK).max()
    )
    data["prior20_low"] = (
        data["low"].shift(1).rolling(BREAKOUT_LOOKBACK).min()
    )
    data["prior5_high"] = (
        data["high"].shift(1).rolling(NARROW_LOOKBACK).max()
    )
    data["prior5_low"] = (
        data["low"].shift(1).rolling(NARROW_LOOKBACK).min()
    )
    data["prior5_volume_mean"] = (
        data["volume"].shift(1).rolling(NARROW_LOOKBACK).mean()
    )
    daily_range = (data["high"] - data["low"]) / data["close"]
    data["prior5_all_narrow"] = (
        daily_range.lt(NARROW_RANGE_MAX)
        .shift(1)
        .rolling(NARROW_LOOKBACK)
        .sum()
        .eq(NARROW_LOOKBACK)
    )
    volume_ok = data["volume"].ge(
        VOLUME_MULTIPLIER * data["prior5_volume_mean"]
    )
    data["a_long"] = (
        data["trend"].eq(1)
        & data["close"].gt(data["prior20_high"])
        & data["return_1d"].gt(IMPULSE_MIN)
        & volume_ok
    )
    data["a_short"] = (
        data["trend"].eq(-1)
        & data["close"].lt(data["prior20_low"])
        & data["return_1d"].lt(-IMPULSE_MIN)
        & volume_ok
    )
    data["b_long"] = (
        data["trend"].eq(1)
        & data["prior5_all_narrow"]
        & data["close"].gt(data["prior5_high"])
        & data["return_1d"].gt(0)
        & data["return_1d"].le(IMPULSE_MIN)
        & volume_ok
    )
    data["b_short"] = (
        data["trend"].eq(-1)
        & data["prior5_all_narrow"]
        & data["close"].lt(data["prior5_low"])
        & data["return_1d"].lt(0)
        & data["return_1d"].ge(-IMPULSE_MIN)
        & volume_ok
    )
    return data


def signal_for(row: pd.Series, variant: Variant) -> tuple[int, str]:
    long_a = variant.use_a and bool(row["a_long"])
    short_a = variant.use_a and bool(row["a_short"])
    long_b = variant.use_b and bool(row["b_long"])
    short_b = variant.use_b and bool(row["b_short"])
    if long_a or long_b:
        return 1, "A" if long_a else "B"
    if short_a or short_b:
        return -1, "A" if short_a else "B"
    return 0, ""


def max_drawdown(values: pd.Series) -> float:
    if values.empty:
        return math.nan
    return float((values / values.cummax() - 1.0).min())


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return math.inf if numerator > 0 else math.nan
    return numerator / denominator


def fill_price(price: float, order_side: int) -> float:
    return price * (1.0 + order_side * SLIPPAGE_PER_FILL)


def backtest(data: pd.DataFrame, variant: Variant) -> dict[str, Any]:
    equity = 1.0
    qty = 0.0
    position_side = 0
    stop_price = math.nan
    entry_atr = math.nan
    initial_fill = math.nan
    tranche_count = 0
    pending_entry = 0
    pending_signal_type = ""
    pending_exit = False
    pending_add = False
    campaign: dict[str, Any] | None = None
    trades: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []
    trade_id = 0
    fees_paid = 0.0
    funding_paid = 0.0
    turnover = 0.0

    def execute_open(
        raw_price: float,
        order_side: int,
        weight: float,
        ts: pd.Timestamp,
        event_type: str,
    ) -> float:
        nonlocal equity, qty, fees_paid, turnover
        effective = fill_price(raw_price, order_side)
        notional = max(equity, 0.0) * weight
        added_qty = order_side * notional / effective
        fee = notional * FEE_PER_FILL
        equity -= fee
        equity += added_qty * (raw_price - effective)
        fees_paid += fee
        turnover += notional
        qty += added_qty
        events.append(
            {
                "trade_id": trade_id,
                "ts": ts,
                "event": event_type,
                "side": "long" if order_side > 0 else "short",
                "raw_price": raw_price,
                "fill_price": effective,
                "notional": notional,
                "fee": fee,
            }
        )
        return effective

    def execute_close(
        raw_price: float,
        current_mark: float,
        ts: pd.Timestamp,
        reason: str,
    ) -> None:
        nonlocal equity, qty, position_side, fees_paid, turnover
        nonlocal campaign, tranche_count, stop_price
        if position_side == 0 or qty == 0:
            return
        effective = fill_price(raw_price, -position_side)
        equity += qty * (effective - current_mark)
        notional = abs(qty) * effective
        fee = notional * FEE_PER_FILL
        equity -= fee
        fees_paid += fee
        turnover += notional
        events.append(
            {
                "trade_id": trade_id,
                "ts": ts,
                "event": "exit",
                "side": "long" if position_side > 0 else "short",
                "raw_price": raw_price,
                "fill_price": effective,
                "notional": notional,
                "fee": fee,
                "reason": reason,
            }
        )
        if campaign is None:
            raise RuntimeError("position exists without campaign")
        net_return = equity / campaign["entry_equity"] - 1.0
        trades.append(
            {
                **campaign,
                "exit_ts": ts,
                "exit_price": effective,
                "exit_reason": reason,
                "tranches": tranche_count,
                "net_return_pct": net_return * 100.0,
                "exit_equity": equity,
            }
        )
        qty = 0.0
        position_side = 0
        campaign = None
        tranche_count = 0
        stop_price = math.nan

    for i, row in data.iterrows():
        ts = pd.Timestamp(row["ts"])
        open_price = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        action_parts: list[str] = []

        if i == 0:
            prior_mark = open_price
        else:
            prior_mark = float(data.iloc[i - 1]["close"])
            equity += qty * (open_price - prior_mark)

        if pending_exit and position_side != 0:
            execute_close(open_price, open_price, ts, "opposite_trend_next_open")
            action_parts.append("exit_opposite_trend")
        pending_exit = False

        if pending_entry != 0 and position_side == 0:
            trade_id += 1
            position_side = pending_entry
            entry_atr = float(data.iloc[i - 1]["atr"])
            entry_equity = equity
            initial_fill = execute_open(
                open_price,
                position_side,
                TRANCHE_WEIGHTS[0],
                ts,
                "entry",
            )
            tranche_count = 1
            stop_price = initial_fill - position_side * STOP_ATR * entry_atr
            campaign = {
                "trade_id": trade_id,
                "side": "long" if position_side > 0 else "short",
                "signal_type": pending_signal_type,
                "signal_ts": pd.Timestamp(data.iloc[i - 1]["ts"]),
                "entry_ts": ts,
                "entry_price": initial_fill,
                "entry_equity": entry_equity,
                "entry_atr": entry_atr,
            }
            action_parts.append(f"entry_{pending_signal_type}")
        pending_entry = 0
        pending_signal_type = ""

        if pending_add and position_side != 0 and variant.pyramiding:
            weight = TRANCHE_WEIGHTS[tranche_count]
            execute_open(
                open_price, position_side, weight, ts, f"add_{tranche_count}"
            )
            tranche_count += 1
            action_parts.append("add")
        pending_add = False

        stopped = False
        if position_side > 0 and low <= stop_price:
            raw_stop = min(open_price, stop_price)
            execute_close(raw_stop, open_price, ts, "stop_or_trail")
            action_parts.append("stop")
            stopped = True
        elif position_side < 0 and high >= stop_price:
            raw_stop = max(open_price, stop_price)
            execute_close(raw_stop, open_price, ts, "stop_or_trail")
            action_parts.append("stop")
            stopped = True

        if not stopped and position_side != 0:
            equity += qty * (close - open_price)
            funding_cashflow = (
                -position_side
                * abs(qty)
                * close
                * float(row["funding_rate_sum"])
            )
            equity += funding_cashflow
            funding_paid -= funding_cashflow

        exposure = (
            abs(qty) * close / equity
            if position_side != 0 and equity > 0
            else 0.0
        )
        path_rows.append(
            {
                "ts": ts,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": float(row["volume"]),
                "sma": row["sma"],
                "atr": row["atr"],
                "trend": int(row["trend"]),
                "a_long": bool(row["a_long"]),
                "a_short": bool(row["a_short"]),
                "b_long": bool(row["b_long"]),
                "b_short": bool(row["b_short"]),
                "position_side": position_side,
                "exposure": exposure,
                "stop": stop_price if position_side != 0 else math.nan,
                "equity": equity,
                "action": ";".join(action_parts) if action_parts else "hold",
            }
        )

        if position_side != 0:
            if int(row["trend"]) == -position_side:
                pending_exit = True
            if (
                variant.pyramiding
                and tranche_count < len(TRANCHE_WEIGHTS)
                and np.isfinite(entry_atr)
            ):
                next_level = ADD_ATR_LEVELS[tranche_count - 1]
                threshold = (
                    initial_fill + position_side * next_level * entry_atr
                )
                if (
                    position_side > 0
                    and close >= threshold
                    or position_side < 0
                    and close <= threshold
                ):
                    pending_add = True
            if np.isfinite(float(row["atr"])):
                candidate = close - position_side * STOP_ATR * float(row["atr"])
                if position_side > 0:
                    stop_price = max(stop_price, candidate)
                else:
                    stop_price = min(stop_price, candidate)
        else:
            signal, signal_type = signal_for(row, variant)
            if signal != 0 and np.isfinite(float(row["atr"])):
                pending_entry = signal
                pending_signal_type = signal_type

    if position_side != 0:
        last = data.iloc[-1]
        execute_close(
            float(last["close"]),
            float(last["close"]),
            pd.Timestamp(last["ts"]) + pd.Timedelta(days=1),
            "period_end_mark",
        )
        path_rows[-1]["equity"] = equity
        path_rows[-1]["position_side"] = 0
        path_rows[-1]["exposure"] = 0.0
        path_rows[-1]["action"] = (
            str(path_rows[-1]["action"]) + ";period_end_mark"
        )

    path = pd.DataFrame(path_rows)
    trade_frame = pd.DataFrame(trades)
    elapsed_days = max(
        1, int((path["ts"].iloc[-1] - path["ts"].iloc[0]).days)
    )
    daily_returns = path["equity"].pct_change().dropna()
    downside = daily_returns.loc[daily_returns < 0]
    trade_returns = (
        trade_frame["net_return_pct"] / 100.0
        if not trade_frame.empty
        else pd.Series(dtype=float)
    )
    positive = float(trade_returns.loc[trade_returns > 0].sum())
    negative = abs(float(trade_returns.loc[trade_returns < 0].sum()))
    underlying_return = (
        float(data["close"].iloc[-1]) / float(data["open"].iloc[0]) - 1.0
    )
    benchmark_returns = {
        weight: (
            weight * underlying_return
            - 2 * weight * (FEE_PER_FILL + SLIPPAGE_PER_FILL)
        )
        for weight in (TRANCHE_WEIGHTS[0], sum(TRANCHE_WEIGHTS))
    }
    metrics = {
        "variant": variant.name,
        "ma_days": variant.ma_days,
        "use_a": variant.use_a,
        "use_b": variant.use_b,
        "pyramiding": variant.pyramiding,
        "start_ts": path["ts"].iloc[0],
        "end_ts": path["ts"].iloc[-1],
        "bars": int(len(path)),
        "net_return_pct": (equity - 1.0) * 100.0,
        "cagr_pct": (equity ** (365.25 / elapsed_days) - 1.0) * 100.0,
        "max_drawdown_pct": max_drawdown(path["equity"]) * 100.0,
        "sharpe": (
            float(daily_returns.mean() / daily_returns.std() * math.sqrt(365.25))
            if daily_returns.std() > 0
            else math.nan
        ),
        "sortino": (
            float(
                daily_returns.mean()
                / downside.std()
                * math.sqrt(365.25)
            )
            if downside.std() > 0
            else math.nan
        ),
        "closed_trades": int(len(trades)),
        "win_rate_pct": (
            float(trade_returns.gt(0).mean() * 100.0)
            if len(trade_returns)
            else math.nan
        ),
        "profit_factor": safe_div(positive, negative),
        "avg_trade_pct": (
            float(trade_returns.mean() * 100.0)
            if len(trade_returns)
            else math.nan
        ),
        "max_exposure_pct": float(path["exposure"].max() * 100.0),
        "time_in_market_pct": float(
            path["position_side"].ne(0).mean() * 100.0
        ),
        "fees_paid_equity": fees_paid,
        "funding_paid_equity": funding_paid,
        "turnover_equity": turnover,
        "benchmark_20pct_buy_hold_return_pct": benchmark_returns[
            TRANCHE_WEIGHTS[0]
        ]
        * 100.0,
        "benchmark_40pct_buy_hold_return_pct": benchmark_returns[
            sum(TRANCHE_WEIGHTS)
        ]
        * 100.0,
        "a_signal_count": int(
            (
                data["a_long"].astype(int) + data["a_short"].astype(int)
            ).sum()
        ),
        "b_signal_count": int(
            (
                data["b_long"].astype(int) + data["b_short"].astype(int)
            ).sum()
        ),
    }
    return {
        "metrics": metrics,
        "path": path,
        "trades": trade_frame,
        "events": pd.DataFrame(events),
    }


def recent_slices(path: pd.DataFrame) -> pd.DataFrame:
    windows = (
        ("1d", 1),
        ("7d", 7),
        ("1m", 30),
        ("3m", 90),
        ("6m", 180),
        ("1y", 365),
    )
    end = pd.Timestamp(path["ts"].iloc[-1])
    rows: list[dict[str, Any]] = []
    for label, days in windows:
        start = end - pd.Timedelta(days=days - 1)
        part = path.loc[path["ts"].ge(start)].copy()
        if part.empty:
            continue
        prior = path.loc[path["ts"].lt(part["ts"].iloc[0]), "equity"]
        start_equity = float(prior.iloc[-1]) if len(prior) else 1.0
        curve = pd.concat(
            [
                pd.Series([start_equity], dtype=float),
                part["equity"].reset_index(drop=True),
            ],
            ignore_index=True,
        )
        rows.append(
            {
                "window": label,
                "start_ts": part["ts"].iloc[0],
                "end_ts": part["ts"].iloc[-1],
                "bars": int(len(part)),
                "net_return_pct": (
                    float(part["equity"].iloc[-1]) / start_equity - 1.0
                )
                * 100.0,
                "max_drawdown_pct": max_drawdown(curve) * 100.0,
            }
        )
    return pd.DataFrame(rows)


def validate_chart_inputs(
    path: pd.DataFrame, trades: pd.DataFrame, metrics: dict[str, Any]
) -> None:
    if path.empty:
        raise RuntimeError("chart path is empty")
    if len(trades) != int(metrics["closed_trades"]):
        raise RuntimeError("chart trade count differs from closed_trades")
    if not trades.empty:
        if trades["trade_id"].duplicated().any():
            raise RuntimeError("duplicate trade ids")
        if (
            pd.to_datetime(trades["entry_ts"], utc=True)
            > pd.to_datetime(trades["exit_ts"], utc=True)
        ).any():
            raise RuntimeError("trade entry after exit")
        if trades[["entry_price", "exit_price"]].isna().any().any():
            raise RuntimeError("trade endpoint missing")


def render_chart(
    path: pd.DataFrame, trades: pd.DataFrame, metrics: dict[str, Any]
) -> str:
    validate_chart_inputs(path, trades, metrics)
    bars = [
        {
            "t": pd.Timestamp(row.ts).isoformat(),
            "o": float(row.open),
            "h": float(row.high),
            "l": float(row.low),
            "c": float(row.close),
            "sma": None if pd.isna(row.sma) else float(row.sma),
            "eq": float(row.equity),
            "act": str(row.action),
        }
        for row in path.itertuples(index=False)
    ]
    trade_rows = [
        {
            "id": int(row.trade_id),
            "side": str(row.side),
            "signal": str(row.signal_type),
            "entryT": pd.Timestamp(row.entry_ts).isoformat(),
            "exitT": pd.Timestamp(row.exit_ts).isoformat(),
            "entry": float(row.entry_price),
            "exit": float(row.exit_price),
            "ret": float(row.net_return_pct),
            "reason": str(row.exit_reason),
            "tranches": int(row.tranches),
        }
        for row in trades.itertuples(index=False)
    ]
    payload = json.dumps(
        {"bars": bars, "trades": trade_rows, "metrics": clean_json(metrics)},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    template = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BTC 青泽临界点趋势策略交易路径</title>
<style>
body{margin:0;background:#0b1020;color:#dbe6ff;font:13px system-ui,sans-serif}
header{padding:18px 22px;border-bottom:1px solid #24304d}
h1{font-size:18px;margin:0 0 8px}.muted{color:#8fa2c9}
#wrap{padding:14px 18px}canvas{width:100%;height:620px;background:#0e1629;border:1px solid #263451}
#tip{position:fixed;display:none;background:#111b31;border:1px solid #516489;padding:8px;pointer-events:none;white-space:pre}
table{width:100%;border-collapse:collapse;margin-top:14px}th,td{padding:7px;border-bottom:1px solid #24304d;text-align:right}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}
tr:hover{background:#18233c;cursor:pointer}.long{color:#40d39c}.short{color:#ff6b7a}
</style></head><body>
<header><h1>BTC-1D-Qingze-Critical-Point-Trend · 交易路径</h1>
<div class="muted" id="summary"></div></header>
<div id="wrap"><canvas id="chart"></canvas><div class="muted">滚轮缩放 · 拖拽平移 · 悬停查看 · 点击交易聚焦。上图：K线 / SMA / 每笔入出场连线；下图：净值。</div>
<table><thead><tr><th>ID</th><th>方向/信号</th><th>入场</th><th>出场</th><th>收益</th><th>层数</th><th>退出</th></tr></thead><tbody id="rows"></tbody></table></div><div id="tip"></div>
<script>
const D=__PAYLOAD__, bars=D.bars, trades=D.trades, m=D.metrics;
const c=document.getElementById('chart'),x=c.getContext('2d'),tip=document.getElementById('tip');
document.getElementById('summary').textContent=`${m.start_ts} → ${m.end_ts} | 净收益 ${m.net_return_pct.toFixed(2)}% | MDD ${m.max_drawdown_pct.toFixed(2)}% | ${m.closed_trades} 笔`;
document.getElementById('rows').innerHTML=trades.map(t=>`<tr data-id="${t.id}"><td>${t.id}</td><td class="${t.side}">${t.side}/${t.signal}</td><td>${t.entryT.slice(0,10)} @ ${t.entry.toFixed(1)}</td><td>${t.exitT.slice(0,10)} @ ${t.exit.toFixed(1)}</td><td>${t.ret.toFixed(2)}%</td><td>${t.tranches}</td><td>${t.reason}</td></tr>`).join('');
let start=0,end=bars.length-1,drag=false,lastX=0;
function size(){c.width=c.clientWidth*devicePixelRatio;c.height=c.clientHeight*devicePixelRatio;x.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);draw()}
function idx(ts){const z=Date.parse(ts);let best=0,d=Infinity;bars.forEach((b,i)=>{const q=Math.abs(Date.parse(b.t)-z);if(q<d){d=q;best=i}});return best}
function draw(){const W=c.clientWidth,H=c.clientHeight,pad=48,split=455,n=Math.max(2,end-start+1),pw=W-pad*2;
x.clearRect(0,0,W,H);const view=bars.slice(start,end+1),lo=Math.min(...view.map(b=>b.l)),hi=Math.max(...view.map(b=>b.h)),emin=Math.min(...view.map(b=>b.eq)),emax=Math.max(...view.map(b=>b.eq));
const X=i=>pad+(i-start+.5)*pw/n,Y=v=>18+(hi-v)/(hi-lo)*410,E=v=>492+(emax-v)/(Math.max(1e-9,emax-emin))*100;
x.strokeStyle='#22304c';x.beginPath();for(let k=0;k<6;k++){let y=18+k*82;x.moveTo(pad,y);x.lineTo(W-pad,y)}x.stroke();
view.forEach((b,j)=>{const i=start+j,xx=X(i),up=b.c>=b.o;x.strokeStyle=up?'#35c690':'#ef6574';x.fillStyle=x.strokeStyle;x.beginPath();x.moveTo(xx,Y(b.h));x.lineTo(xx,Y(b.l));x.stroke();const y=Math.min(Y(b.o),Y(b.c)),hh=Math.max(1,Math.abs(Y(b.o)-Y(b.c)));x.fillRect(xx-Math.max(1,pw/n*.28),y,Math.max(2,pw/n*.56),hh)});
x.strokeStyle='#f2c14e';x.lineWidth=1.4;x.beginPath();let on=false;view.forEach((b,j)=>{if(b.sma==null)return;const xx=X(start+j),yy=Y(b.sma);on?x.lineTo(xx,yy):x.moveTo(xx,yy);on=true});x.stroke();
trades.forEach(t=>{const a=idx(t.entryT),b=idx(t.exitT);if(b<start||a>end)return;x.strokeStyle=t.side==='long'?'#40d39c':'#ff6b7a';x.lineWidth=2;x.beginPath();x.moveTo(X(a),Y(t.entry));x.lineTo(X(b),Y(t.exit));x.stroke();x.fillStyle=x.strokeStyle;[ [a,t.entry],[b,t.exit] ].forEach(q=>{x.beginPath();x.arc(X(q[0]),Y(q[1]),4,0,Math.PI*2);x.fill()})});
x.strokeStyle='#74a7ff';x.lineWidth=1.7;x.beginPath();view.forEach((b,j)=>{const xx=X(start+j),yy=E(b.eq);j?x.lineTo(xx,yy):x.moveTo(xx,yy)});x.stroke();
x.fillStyle='#8fa2c9';x.fillText(hi.toFixed(0),4,25);x.fillText(lo.toFixed(0),4,425);x.fillText('Equity',4,505)}
c.addEventListener('wheel',e=>{e.preventDefault();const span=end-start+1,focus=start+Math.floor((e.offsetX/c.clientWidth)*span),next=Math.max(25,Math.min(bars.length,Math.round(span*(e.deltaY>0?1.25:.8))));start=Math.max(0,Math.min(bars.length-next,focus-Math.floor(next*(e.offsetX/c.clientWidth))));end=start+next-1;draw()},{passive:false});
c.addEventListener('mousedown',e=>{drag=true;lastX=e.clientX});addEventListener('mouseup',()=>drag=false);c.addEventListener('mousemove',e=>{if(drag){const span=end-start+1,shift=Math.round((lastX-e.clientX)/c.clientWidth*span);if(shift){start=Math.max(0,Math.min(bars.length-span,start+shift));end=start+span-1;lastX=e.clientX;draw()}return}const i=Math.max(start,Math.min(end,start+Math.floor((e.offsetX-48)/(c.clientWidth-96)*(end-start+1))));const b=bars[i];tip.style.display='block';tip.style.left=e.clientX+12+'px';tip.style.top=e.clientY+12+'px';tip.textContent=`${b.t.slice(0,10)}\nO ${b.o} H ${b.h}\nL ${b.l} C ${b.c}\nSMA ${b.sma??'n/a'}\nEquity ${b.eq.toFixed(4)}\n${b.act}`});c.addEventListener('mouseleave',()=>tip.style.display='none');
document.querySelectorAll('tbody tr').forEach(r=>r.onclick=()=>{const t=trades.find(q=>q.id==r.dataset.id),mid=Math.floor((idx(t.entryT)+idx(t.exitT))/2),span=Math.max(40,idx(t.exitT)-idx(t.entryT)+30);start=Math.max(0,mid-Math.floor(span/2));end=Math.min(bars.length-1,start+span);start=Math.max(0,end-span);draw()});
addEventListener('resize',size);size();
</script></body></html>"""
    return template.replace("__PAYLOAD__", payload)


def self_test() -> None:
    dates = pd.date_range("2024-01-01", periods=120, freq="1D", tz="UTC")
    close = np.linspace(100.0, 180.0, len(dates))
    data = pd.DataFrame(
        {
            "ts": dates,
            "open": close * 0.995,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.where(np.arange(len(dates)) == 80, 300.0, 100.0),
            "quote_volume": close * 100.0,
            "trade_count": 1000,
            "funding_rate_sum": 0.0,
            "funding_events": 3,
        }
    )
    featured = add_features(data, 55)
    assert featured["trend"].iloc[-1] == 1
    result = backtest(featured, Variant("test", 55, True, True))
    assert len(result["path"]) == len(data)
    print("self-test: PASS")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    hourly, funding, quality = load_and_audit()
    daily = aggregate_daily(hourly, funding)
    quality["daily_rows"] = int(len(daily))
    quality["first_complete_day"] = daily["ts"].iloc[0].isoformat()
    quality["last_complete_day"] = daily["ts"].iloc[-1].isoformat()
    quality["days_without_funding_events"] = int(
        daily["funding_events"].eq(0).sum()
    )
    oi_dates = sorted(OI_ROOT.glob("date=*"))
    quality["open_interest"] = {
        "available_daily_partitions": int(len(oi_dates)),
        "first_partition": oi_dates[0].name if oi_dates else None,
        "last_partition": oi_dates[-1].name if oi_dates else None,
        "usable_for_20d_filter": False,
        "treatment": (
            "not used; insufficient coverage, and volume is not treated as "
            "an open-interest proxy"
        ),
    }

    results: dict[str, dict[str, Any]] = {}
    metric_rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        featured = add_features(daily, variant.ma_days)
        result = backtest(featured, variant)
        results[variant.name] = result
        metric_rows.append(result["metrics"])
    metrics = pd.DataFrame(metric_rows)
    base = results[BASE_VARIANT]
    recent = recent_slices(base["path"])
    validate_chart_inputs(base["path"], base["trades"], base["metrics"])

    stem = "btc_1d_qingze_critical_point"
    summary_path = ARTIFACT_DIR / f"{stem}_summary_{args.run_date}.json"
    metrics_path = ARTIFACT_DIR / f"{stem}_metrics_{args.run_date}.csv"
    recent_path = ARTIFACT_DIR / f"{stem}_recent_{args.run_date}.csv"
    trades_path = ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv"
    events_path = ARTIFACT_DIR / f"{stem}_events_{args.run_date}.csv"
    path_path = ARTIFACT_DIR / f"{stem}_path_{args.run_date}.csv"
    chart_path = ARTIFACT_DIR / f"{stem}_trade_path_{args.run_date}.html"

    metrics.to_csv(metrics_path, index=False)
    recent.to_csv(recent_path, index=False)
    base["trades"].to_csv(trades_path, index=False)
    base["events"].to_csv(events_path, index=False)
    base["path"].to_csv(path_path, index=False)
    chart_path.write_text(
        render_chart(base["path"], base["trades"], base["metrics"]),
        encoding="utf-8",
    )
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "run_date": args.run_date,
        "family": "BTC-1D-Qingze-Critical-Point-Trend",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "one_sentence": (
            "用 SMA55/60 只定多空方向，在放量突破临界点后次日开盘试仓，"
            "仅在浮盈中按正金字塔加码，并用宽 ATR 追踪止损控制灾难性亏损。"
        ),
        "data_quality": quality,
        "contract": {
            "market": "Binance USD-M perpetual",
            "symbol": SYMBOL,
            "timeframe": "UTC 1d aggregated from accepted 1h bars",
            "trend": (
                "three closes on the same side of SMA, current deviation at "
                "least 1.5%, and SMA slope aligned"
            ),
            "a_signal": (
                "close breaks prior 20d extreme, abs daily return >2%, "
                "volume >=1.5x prior 5d mean"
            ),
            "b_signal": (
                "prior five daily ranges each <1.5%, close breaks prior 5d "
                "extreme with abs daily return <=2%, volume >=1.5x prior 5d mean"
            ),
            "open_interest": (
                "required by the narrative but omitted from the main test "
                "because local coverage is only eight days"
            ),
            "execution": (
                "closed-day signal; enter/add/exit on next UTC-day open; "
                "gap-aware intraday stop using daily OHLC"
            ),
            "position_sizing": {
                "tranches_of_current_equity": list(TRANCHE_WEIGHTS),
                "add_levels_atr_from_initial_fill": list(ADD_ATR_LEVELS),
                "maximum_nominal_allocation": sum(TRANCHE_WEIGHTS),
            },
            "risk": {
                "initial_stop_atr": STOP_ATR,
                "causal_close_trailing_stop_atr": STOP_ATR,
                "opposite_trend_exit": "next open",
            },
            "costs": {
                "fee_per_fill": FEE_PER_FILL,
                "slippage_per_fill": SLIPPAGE_PER_FILL,
                "funding": (
                    "actual daily sum, charged on end-of-day held notional; "
                    "intraday stop timing remains approximated"
                ),
            },
            "selection": (
                "no parameter optimization; all variants are prespecified "
                "interpretation/sensitivity checks"
            ),
        },
        "base_variant": BASE_VARIANT,
        "variants": [asdict(item) for item in VARIANTS],
        "metrics": clean_json(metric_rows),
        "recent_slices": clean_json(recent.to_dict("records")),
        "artifacts": {
            "summary": str(summary_path.relative_to(ROOT)),
            "metrics": str(metrics_path.relative_to(ROOT)),
            "recent": str(recent_path.relative_to(ROOT)),
            "trades": str(trades_path.relative_to(ROOT)),
            "events": str(events_path.relative_to(ROOT)),
            "path": str(path_path.relative_to(ROOT)),
            "trade_path_html": str(chart_path.relative_to(ROOT)),
        },
    }
    summary_path.write_text(
        json.dumps(
            clean_json(payload),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    print(metrics.to_string(index=False))
    print(recent.to_string(index=False))
    print(f"Wrote {summary_path}")
    print(f"Wrote {chart_path}")


if __name__ == "__main__":
    main()
