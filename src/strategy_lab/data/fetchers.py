from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from strategy_lab.data.models import MarketType


def _to_millis(value: datetime | None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def _timeframe_millis(value: str) -> int:
    suffix = value[-1]
    amount = int(value[:-1])
    if suffix == "m":
        return amount * 60 * 1000
    if suffix == "h":
        return amount * 60 * 60 * 1000
    if suffix == "d":
        return amount * 24 * 60 * 60 * 1000
    raise ValueError(f"unsupported timeframe: {value}")


def _split_symbol(symbol: str) -> tuple[str, str]:
    base, quote = symbol.split("/", maxsplit=1)
    quote = quote.split(":", maxsplit=1)[0]
    return base.upper(), quote.upper()


def _extract_timestamp(payload: dict[str, Any]) -> pd.Timestamp:
    value = payload.get("timestamp") or payload.get("fundingTimestamp") or payload.get("datetime")
    return pd.to_datetime(value, unit="ms", utc=True) if isinstance(value, (int, float)) else pd.to_datetime(value, utc=True)


def _extract_float(payload: dict[str, Any], candidates: list[str]) -> float | None:
    for key in candidates:
        if key in payload and payload[key] is not None:
            return float(payload[key])
    return None


def _binance_pair(symbol: str) -> str:
    base_asset, quote_asset = _split_symbol(symbol)
    return f"{base_asset}{quote_asset}"


def _market_id(exchange: Any, symbol: str) -> str:
    try:
        if getattr(exchange, "markets", None) is None:
            exchange.load_markets()
        return str(exchange.market(symbol)["id"])
    except Exception:
        return _binance_pair(symbol)


def _to_seconds(value: datetime | None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


def _historical_liquidation_row(
    *,
    ts: pd.Timestamp,
    exchange_name: str,
    symbol: str,
    market_type: MarketType,
    base_asset: str,
    quote_asset: str,
    side: str,
    liquidation_side: str,
    price: float,
    notional: float,
) -> dict[str, Any]:
    size = notional / price if price else 0.0
    return {
        "ts": ts,
        "exchange": exchange_name,
        "symbol": symbol.upper(),
        "market_type": market_type.value,
        "base_asset": base_asset,
        "quote_asset": quote_asset,
        "side": side,
        "liquidation_side": liquidation_side,
        "price": price,
        "size": size,
        "filled_quantity": size,
        "notional": notional,
        "source": "gateio_contract_stats",
    }


@dataclass(slots=True)
class CCXTDataClient:
    exchange_name: str
    market_type: MarketType = MarketType.SPOT
    _exchange: Any | None = field(default=None, init=False, repr=False)

    def _build_exchange(self):
        import ccxt

        exchange_class = getattr(ccxt, self.exchange_name)
        default_type = "swap" if self.market_type == MarketType.PERP else "spot"
        return exchange_class({"enableRateLimit": True, "options": {"defaultType": default_type}})

    def _get_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_exchange()
        return self._exchange

    def load_markets(self) -> dict[str, dict[str, Any]]:
        exchange = self._get_exchange()
        return exchange.load_markets()

    def fetch_tickers(self, symbols: list[str] | None = None) -> dict[str, dict[str, Any]]:
        exchange = self._get_exchange()
        method = getattr(exchange, "fetch_tickers", None)
        if method is None:
            raise NotImplementedError(f"{self.exchange_name} does not expose fetch_tickers in ccxt")
        return method(symbols)

    def fetch_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str = "1h",
        since: datetime | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        exchange = self._get_exchange()
        if self.exchange_name == "binance" and self.market_type == MarketType.SPOT and hasattr(exchange, "publicGetKlines"):
            return self._fetch_binance_spot_ohlcv(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=limit,
            )
        since_ms = _to_millis(since)
        if since_ms is None:
            raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=None, limit=limit)
        else:
            raw = []
            step_ms = _timeframe_millis(timeframe)
            next_since = since_ms
            remaining = limit
            while remaining > 0:
                batch_limit = min(1000, remaining)
                batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=next_since, limit=batch_limit)
                if not batch:
                    break
                raw.extend(batch)
                remaining -= len(batch)
                last_ts = int(batch[-1][0])
                candidate_since = last_ts + step_ms
                if candidate_since <= next_since:
                    break
                next_since = candidate_since
        frame = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
        if frame.empty:
            return self._empty_ohlcv_frame(symbol=symbol)
        frame["ts"] = pd.to_datetime(frame["ts"], unit="ms", utc=True)
        frame = frame.drop_duplicates(subset=["ts"]).sort_values("ts").reset_index(drop=True)
        base_asset, quote_asset = _split_symbol(symbol)
        frame["exchange"] = self.exchange_name
        frame["symbol"] = symbol.upper()
        frame["market_type"] = self.market_type.value
        frame["base_asset"] = base_asset
        frame["quote_asset"] = quote_asset
        frame["quote_volume"] = frame["close"].astype(float) * frame["volume"].astype(float)
        frame["trade_count"] = 0
        frame["vwap"] = frame["quote_volume"] / frame["volume"].replace(0.0, pd.NA)
        frame["is_closed"] = True
        frame["source"] = "ccxt"
        ordered_columns = [
            "ts",
            "exchange",
            "symbol",
            "market_type",
            "base_asset",
            "quote_asset",
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
        return frame[ordered_columns]

    def _empty_ohlcv_frame(self, *, symbol: str) -> pd.DataFrame:
        base_asset, quote_asset = _split_symbol(symbol)
        columns = [
            "ts",
            "exchange",
            "symbol",
            "market_type",
            "base_asset",
            "quote_asset",
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
        frame = pd.DataFrame(columns=columns)
        frame["exchange"] = self.exchange_name
        frame["symbol"] = symbol.upper()
        frame["market_type"] = self.market_type.value
        frame["base_asset"] = base_asset
        frame["quote_asset"] = quote_asset
        frame["source"] = "ccxt"
        return frame[columns]

    def _fetch_binance_spot_ohlcv(
        self,
        *,
        exchange: Any,
        symbol: str,
        timeframe: str,
        since: datetime | None,
        limit: int,
    ) -> pd.DataFrame:
        request_symbol = _market_id(exchange, symbol)
        since_ms = _to_millis(since)
        raw: list[list[Any]] = []
        step_ms = _timeframe_millis(timeframe)
        next_since = since_ms
        remaining = limit
        while remaining > 0:
            batch_limit = min(1000, remaining)
            params: dict[str, Any] = {
                "symbol": request_symbol,
                "interval": timeframe,
                "limit": batch_limit,
            }
            if next_since is not None:
                params["startTime"] = next_since
            batch = exchange.publicGetKlines(params)
            if not batch:
                break
            raw.extend(batch)
            remaining -= len(batch)
            last_ts = int(batch[-1][0])
            candidate_since = last_ts + step_ms
            if next_since is None:
                break
            if candidate_since <= next_since:
                break
            next_since = candidate_since

        if not raw:
            return self._empty_ohlcv_frame(symbol=symbol)

        rows = []
        base_asset, quote_asset = _split_symbol(symbol)
        for item in raw:
            volume = float(item[5])
            quote_volume = float(item[7])
            rows.append(
                {
                    "ts": pd.to_datetime(int(item[0]), unit="ms", utc=True),
                    "exchange": self.exchange_name,
                    "symbol": symbol.upper(),
                    "market_type": self.market_type.value,
                    "base_asset": base_asset,
                    "quote_asset": quote_asset,
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": volume,
                    "quote_volume": quote_volume,
                    "trade_count": int(item[8]),
                    "vwap": quote_volume / volume if volume else float(item[4]),
                    "is_closed": True,
                    "source": "binance_kline_api",
                }
            )
        frame = pd.DataFrame(rows).drop_duplicates(subset=["ts"]).sort_values("ts").reset_index(drop=True)
        return frame[
            [
                "ts",
                "exchange",
                "symbol",
                "market_type",
                "base_asset",
                "quote_asset",
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
        ]

    def fetch_funding_rates(
        self,
        *,
        symbol: str,
        since: datetime | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        exchange = self._get_exchange()
        method = getattr(exchange, "fetch_funding_rate_history", None)
        if method is None:
            raise NotImplementedError(f"{self.exchange_name} does not expose fetch_funding_rate_history in ccxt")

        raw = method(symbol, since=_to_millis(since), limit=limit)
        base_asset, quote_asset = _split_symbol(symbol)
        rows = []
        for item in raw:
            rows.append(
                {
                    "ts": _extract_timestamp(item),
                    "exchange": self.exchange_name,
                    "symbol": symbol.upper(),
                    "market_type": self.market_type.value,
                    "base_asset": base_asset,
                    "quote_asset": quote_asset,
                    "funding_rate": _extract_float(item, ["fundingRate", "funding_rate"]),
                    "next_funding_ts": pd.to_datetime(item.get("nextFundingTimestamp"), unit="ms", utc=True)
                    if item.get("nextFundingTimestamp") is not None
                    else pd.NaT,
                    "source": "ccxt",
                }
            )
        return pd.DataFrame(rows)

    def fetch_open_interest(
        self,
        *,
        symbol: str,
        timeframe: str = "1h",
        since: datetime | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        exchange = self._get_exchange()
        base_asset, quote_asset = _split_symbol(symbol)

        if self.exchange_name == "gateio" and self.market_type == MarketType.PERP:
            market = exchange.market(symbol) if getattr(exchange, "markets", None) else exchange.load_markets()[symbol]
            request: dict[str, Any] = {
                "contract": market["id"],
                "settle": market["settleId"],
                "interval": timeframe,
                "limit": limit,
            }
            seconds = _to_seconds(since)
            if seconds is not None:
                request["from"] = seconds
            raw = exchange.publicFuturesGetSettleContractStats(request)
            rows = []
            for item in raw:
                rows.append(
                    {
                        "ts": pd.to_datetime(int(item["time"]), unit="s", utc=True),
                        "exchange": self.exchange_name,
                        "symbol": symbol.upper(),
                        "market_type": self.market_type.value,
                        "base_asset": base_asset,
                        "quote_asset": quote_asset,
                        "open_interest": _extract_float(item, ["open_interest_usd", "open_interest"]),
                        "open_interest_value": _extract_float(item, ["open_interest_usd"]),
                        "source": "gateio_contract_stats",
                    }
                )
            return pd.DataFrame(rows)

        method = getattr(exchange, "fetch_open_interest_history", None)
        if method is None:
            raise NotImplementedError(f"{self.exchange_name} does not expose fetch_open_interest_history in ccxt")

        raw = method(symbol, timeframe=timeframe, since=_to_millis(since), limit=limit)
        rows = []
        for item in raw:
            rows.append(
                {
                    "ts": _extract_timestamp(item),
                    "exchange": self.exchange_name,
                    "symbol": symbol.upper(),
                    "market_type": self.market_type.value,
                    "base_asset": base_asset,
                    "quote_asset": quote_asset,
                    "open_interest": _extract_float(
                        item,
                        ["openInterestAmount", "openInterest", "open_interest", "openInterestValue", "open_interest_value"],
                    ),
                    "open_interest_value": _extract_float(item, ["openInterestValue", "open_interest_value"]),
                    "source": "ccxt",
                }
            )
        return pd.DataFrame(rows)

    def fetch_basis_or_premium(
        self,
        *,
        symbol: str,
        timeframe: str = "1h",
        since: datetime | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        exchange = self._get_exchange()
        base_asset, quote_asset = _split_symbol(symbol)
        rows_by_ts: dict[pd.Timestamp, dict[str, Any]] = {}
        basis_error: Exception | None = None
        premium_error: Exception | None = None

        if self.exchange_name == "binance" and self.market_type == MarketType.PERP:
            method = getattr(exchange, "fapiDataGetBasis", None)
            if method is None:
                raise NotImplementedError("binance perp basis endpoint is unavailable in this ccxt build")

            params: dict[str, Any] = {
                "pair": _binance_pair(symbol),
                "contractType": "PERPETUAL",
                "period": timeframe,
                "limit": limit,
            }
            if since is not None:
                params["startTime"] = _to_millis(since)
            try:
                raw_basis = method(params)
                for item in raw_basis:
                    ts = _extract_timestamp(item)
                    rows_by_ts[ts] = {
                        "ts": ts,
                        "exchange": self.exchange_name,
                        "symbol": symbol.upper(),
                        "market_type": self.market_type.value,
                        "base_asset": base_asset,
                        "quote_asset": quote_asset,
                        "basis": _extract_float(item, ["basis"]),
                        "basis_rate": _extract_float(item, ["basisRate", "basis_rate"]),
                        "annualized_basis": _extract_float(item, ["annualizedBasisRate", "annualized_basis"]),
                        "futures_price": _extract_float(item, ["futuresPrice", "futures_price"]),
                        "index_price": _extract_float(item, ["indexPrice", "index_price"]),
                        "mark_price": _extract_float(item, ["markPrice", "mark_price"]),
                        "premium_index": None,
                        "source": "binance_api",
                    }
            except Exception as exc:
                basis_error = exc

        premium_method = getattr(exchange, "fetch_premium_index_ohlcv", None)
        if premium_method is not None:
            try:
                premium_rows = premium_method(symbol, timeframe=timeframe, since=_to_millis(since), limit=limit)
                for candle in premium_rows:
                    ts = pd.to_datetime(candle[0], unit="ms", utc=True)
                    row = rows_by_ts.get(
                        ts,
                        {
                            "ts": ts,
                            "exchange": self.exchange_name,
                            "symbol": symbol.upper(),
                            "market_type": self.market_type.value,
                            "base_asset": base_asset,
                            "quote_asset": quote_asset,
                            "basis": None,
                            "basis_rate": None,
                            "annualized_basis": None,
                            "futures_price": None,
                            "index_price": None,
                            "mark_price": None,
                            "premium_index": None,
                            "source": "ccxt",
                        },
                    )
                    row["premium_index"] = float(candle[4])
                    rows_by_ts[ts] = row
            except Exception as exc:
                premium_error = exc

        if self.exchange_name in {"okx", "gateio"} and not rows_by_ts:
            mark_method = getattr(exchange, "fetch_mark_ohlcv", None)
            index_method = getattr(exchange, "fetch_index_ohlcv", None)
            if mark_method is None or index_method is None:
                raise NotImplementedError(f"{self.exchange_name} mark/index ohlcv endpoints are unavailable in this ccxt build")

            mark_rows = mark_method(symbol, timeframe=timeframe, since=_to_millis(since), limit=limit)
            index_rows = index_method(symbol, timeframe=timeframe, since=_to_millis(since), limit=limit)
            index_lookup = {int(item[0]): item for item in index_rows}
            for mark_candle in mark_rows:
                ts_ms = int(mark_candle[0])
                index_candle = index_lookup.get(ts_ms)
                if index_candle is None:
                    continue
                ts = pd.to_datetime(ts_ms, unit="ms", utc=True)
                mark_close = float(mark_candle[4])
                index_close = float(index_candle[4])
                basis = mark_close - index_close
                basis_rate = basis / index_close if index_close else None
                rows_by_ts[ts] = {
                    "ts": ts,
                    "exchange": self.exchange_name,
                    "symbol": symbol.upper(),
                    "market_type": self.market_type.value,
                    "base_asset": base_asset,
                    "quote_asset": quote_asset,
                    "basis": basis,
                    "basis_rate": basis_rate,
                    "annualized_basis": basis_rate * 365 if basis_rate is not None else None,
                    "futures_price": mark_close,
                    "index_price": index_close,
                    "mark_price": mark_close,
                    "premium_index": basis_rate,
                    "source": f"{self.exchange_name}_mark_index",
                }

        columns = [
            "ts",
            "exchange",
            "symbol",
            "market_type",
            "base_asset",
            "quote_asset",
            "basis",
            "basis_rate",
            "annualized_basis",
            "futures_price",
            "index_price",
            "mark_price",
            "premium_index",
            "source",
        ]
        if not rows_by_ts:
            if basis_error is not None:
                raise basis_error
            if premium_error is not None:
                raise premium_error
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(sorted(rows_by_ts.values(), key=lambda item: item["ts"]))[columns]

    def fetch_historical_liquidations(
        self,
        *,
        symbol: str,
        timeframe: str = "4h",
        since: datetime | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        exchange = self._get_exchange()
        base_asset, quote_asset = _split_symbol(symbol)

        if self.exchange_name != "gateio":
            raise NotImplementedError(f"{self.exchange_name} does not expose a supported historical liquidation source")

        market = exchange.market(symbol) if getattr(exchange, "markets", None) else exchange.load_markets()[symbol]
        request: dict[str, Any] = {
            "contract": market["id"],
            "settle": market["settleId"],
            "interval": timeframe,
            "limit": limit,
        }
        if since is not None:
            request["from"] = _to_seconds(since)
        raw = exchange.publicFuturesGetSettleContractStats(request)

        rows = []
        for item in raw:
            ts = pd.to_datetime(int(item["time"]), unit="s", utc=True)
            price = _extract_float(item, ["mark_price", "markPrice"]) or 0.0
            long_notional = _extract_float(item, ["long_liq_usd_new", "long_liq_usd"]) or 0.0
            short_notional = _extract_float(item, ["short_liq_usd_new", "short_liq_usd"]) or 0.0

            if long_notional > 0:
                rows.append(
                    _historical_liquidation_row(
                        ts=ts,
                        exchange_name=self.exchange_name,
                        symbol=symbol,
                        market_type=self.market_type,
                        base_asset=base_asset,
                        quote_asset=quote_asset,
                        side="sell",
                        liquidation_side="long",
                        price=price,
                        notional=long_notional,
                    )
                )
            if short_notional > 0:
                rows.append(
                    _historical_liquidation_row(
                        ts=ts,
                        exchange_name=self.exchange_name,
                        symbol=symbol,
                        market_type=self.market_type,
                        base_asset=base_asset,
                        quote_asset=quote_asset,
                        side="buy",
                        liquidation_side="short",
                        price=price,
                        notional=short_notional,
                    )
                )

        columns = [
            "ts",
            "exchange",
            "symbol",
            "market_type",
            "base_asset",
            "quote_asset",
            "side",
            "liquidation_side",
            "price",
            "size",
            "filled_quantity",
            "notional",
            "source",
        ]
        return pd.DataFrame(rows, columns=columns)
