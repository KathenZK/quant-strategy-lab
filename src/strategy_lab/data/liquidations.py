from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.data.models import MarketType


def _binance_symbol_to_perp(symbol: str) -> tuple[str, str, str]:
    for quote_asset in ("USDT", "USDC", "BUSD", "FDUSD"):
        if symbol.endswith(quote_asset) and len(symbol) > len(quote_asset):
            base_asset = symbol[: -len(quote_asset)]
            return f"{base_asset}/{quote_asset}:{quote_asset}", base_asset, quote_asset
    return symbol.upper(), symbol.upper(), "UNKNOWN"


def _iter_force_orders(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows: list[dict[str, Any]] = []
        for item in payload:
            rows.extend(_iter_force_orders(item))
        return rows

    if not isinstance(payload, dict):
        return []

    if "data" in payload:
        return _iter_force_orders(payload["data"])

    event_time = payload.get("E") or payload.get("eventTime")
    order = payload.get("o") or payload
    if not isinstance(order, dict):
        return []

    order["__event_time__"] = event_time
    return [order]


def normalize_binance_force_order_events(payload: Any) -> pd.DataFrame:
    rows = []
    for order in _iter_force_orders(payload):
        symbol = str(order.get("s", "")).upper()
        normalized_symbol, base_asset, quote_asset = _binance_symbol_to_perp(symbol)
        event_ts = order.get("T") or order.get("__event_time__")
        price = float(order.get("ap") or order.get("p") or 0.0)
        size = float(order.get("z") or order.get("q") or 0.0)
        side = str(order.get("S", "")).lower()
        liquidation_side = "long" if side == "sell" else "short"
        rows.append(
            {
                "ts": pd.to_datetime(event_ts, unit="ms", utc=True),
                "exchange": "binance",
                "symbol": normalized_symbol,
                "market_type": MarketType.PERP.value,
                "base_asset": base_asset,
                "quote_asset": quote_asset,
                "side": side,
                "liquidation_side": liquidation_side,
                "order_type": str(order.get("o", "")).lower(),
                "time_in_force": str(order.get("f", "")).lower(),
                "price": price,
                "size": size,
                "filled_quantity": size,
                "notional": price * size,
                "source": "binance_force_order_stream",
            }
        )
    return pd.DataFrame(rows)


def aggregate_liquidation_events(events: pd.DataFrame, *, frequency: str = "1h") -> pd.DataFrame:
    columns = [
        "ts",
        "exchange",
        "symbol",
        "market_type",
        "base_asset",
        "quote_asset",
        "liquidation_long_notional",
        "liquidation_short_notional",
        "liquidation_total_notional",
        "liquidation_count",
        "liquidation_imbalance",
    ]
    if events.empty:
        return pd.DataFrame(columns=columns)

    working = events.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True)
    try:
        working["notional"] = pd.to_numeric(working["notional"], errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid numeric value in liquidation notional") from exc
    if working["notional"].isna().any():
        raise ValueError("liquidation notional contains null values")
    working["liquidation_long_notional"] = np.where(working["side"].str.lower() == "sell", working["notional"], 0.0)
    working["liquidation_short_notional"] = np.where(working["side"].str.lower() == "buy", working["notional"], 0.0)
    working["bucket_ts"] = working["ts"].dt.floor(frequency)

    aggregated = (
        working.groupby(
            ["bucket_ts", "exchange", "symbol", "market_type", "base_asset", "quote_asset"],
            dropna=False,
        )
        .agg(
            liquidation_long_notional=("liquidation_long_notional", "sum"),
            liquidation_short_notional=("liquidation_short_notional", "sum"),
            liquidation_total_notional=("notional", "sum"),
            liquidation_count=("ts", "size"),
        )
        .reset_index()
        .rename(columns={"bucket_ts": "ts"})
    )

    total = aggregated["liquidation_total_notional"].replace(0.0, np.nan)
    aggregated["liquidation_imbalance"] = (
        aggregated["liquidation_short_notional"] - aggregated["liquidation_long_notional"]
    ) / total
    aggregated["liquidation_imbalance"] = aggregated["liquidation_imbalance"].fillna(0.0)
    return aggregated[columns]


def enrich_liquidation_features(
    bars: pd.DataFrame,
    *,
    dollar_volume: pd.Series | None = None,
    open_interest: pd.Series | None = None,
    spike_window: int = 24,
    cooldown_bars: int = 3,
    spike_threshold: float = 2.5,
    notional_ratio_threshold: float = 0.03,
) -> pd.DataFrame:
    columns = [
        "ts",
        "exchange",
        "symbol",
        "market_type",
        "base_asset",
        "quote_asset",
        "liquidation_long_notional",
        "liquidation_short_notional",
        "liquidation_total_notional",
        "liquidation_count",
        "liquidation_imbalance",
        "liq_spike_zscore",
        "liq_notional_vs_dollar_volume",
        "post_liq_oi_drop",
        "event_cooldown_flag",
    ]
    if bars.empty:
        return pd.DataFrame(columns=columns)

    features = bars.copy().sort_values("ts").reset_index(drop=True)
    rolling_mean = features["liquidation_total_notional"].rolling(spike_window, min_periods=spike_window).mean()
    rolling_std = features["liquidation_total_notional"].rolling(spike_window, min_periods=spike_window).std()
    features["liq_spike_zscore"] = (
        features["liquidation_total_notional"] - rolling_mean
    ) / rolling_std.replace(0.0, np.nan)
    features["liq_spike_zscore"] = features["liq_spike_zscore"].fillna(0.0)

    if dollar_volume is None:
        features["liq_notional_vs_dollar_volume"] = 0.0
    else:
        aligned_dollar_volume = pd.Series(dollar_volume).reindex(pd.to_datetime(features["ts"], utc=True)).fillna(0.0).to_numpy()
        features["liq_notional_vs_dollar_volume"] = np.where(
            aligned_dollar_volume > 0,
            features["liquidation_total_notional"].to_numpy() / aligned_dollar_volume,
            0.0,
        )

    if open_interest is None:
        features["post_liq_oi_drop"] = 0.0
    else:
        aligned_oi = pd.Series(open_interest).reindex(pd.to_datetime(features["ts"], utc=True)).ffill()
        features["post_liq_oi_drop"] = -aligned_oi.pct_change().fillna(0.0).to_numpy()

    trigger = (
        (features["liq_spike_zscore"] >= spike_threshold)
        | (features["liq_notional_vs_dollar_volume"] >= notional_ratio_threshold)
    ).astype(int)
    features["event_cooldown_flag"] = trigger.rolling(cooldown_bars, min_periods=1).max().fillna(0.0).astype(int)
    return features[columns]


@dataclass(frozen=True, slots=True)
class BinanceLiquidationStreamConfig:
    stream: str = "!forceOrder@arr"
    websocket_url: str = "wss://fstream.binance.com/ws"
