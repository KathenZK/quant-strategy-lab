from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from strategy_lab.data.fetchers import CCXTDataClient
from strategy_lab.data.lake import DataLakeLayout
from strategy_lab.data.liquidation_stream import BinanceLiquidationStreamCollector
from strategy_lab.data.models import DatasetKind, MarketType
from strategy_lab.data.normalize import normalize_dataset
from strategy_lab.data.store import write_dataframe


def _timeframe_delta(value: str) -> pd.Timedelta:
    suffix = value[-1]
    amount = int(value[:-1])
    if suffix == "m":
        return pd.Timedelta(minutes=amount)
    if suffix == "h":
        return pd.Timedelta(hours=amount)
    if suffix == "d":
        return pd.Timedelta(days=amount)
    raise ValueError(f"unsupported timeframe: {value}")


def drop_incomplete_ohlcv(frame: pd.DataFrame, *, timeframe: str, now: pd.Timestamp | None = None) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    current_time = pd.Timestamp.now(tz="UTC") if now is None else pd.to_datetime(now, utc=True)
    close_time = pd.to_datetime(frame["ts"], utc=True) + _timeframe_delta(timeframe)
    return frame.loc[close_time <= current_time].reset_index(drop=True)


def _partition_dates(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["ts"], utc=True).dt.date


def _write_frame_by_date(
    frame: pd.DataFrame,
    *,
    layout: DataLakeLayout,
    layer: str,
    kind: DatasetKind,
    exchange: str,
    market_type: MarketType,
    symbol: str,
    timeframe: str | None = None,
) -> list[str]:
    paths: list[str] = []
    for partition_date, group in frame.groupby(_partition_dates(frame), sort=True):
        path = write_dataframe(
            group.reset_index(drop=True),
            layout=layout,
            layer=layer,
            kind=kind,
            exchange=exchange,
            market_type=market_type,
            symbol=symbol,
            partition_date=partition_date,
            timeframe=timeframe,
        )
        paths.append(str(path))
    return paths


def _write_dataset_pair(
    *,
    layout: DataLakeLayout,
    raw: pd.DataFrame,
    normalized: pd.DataFrame,
    kind: DatasetKind,
    exchange: str,
    market_type: MarketType,
    symbol: str,
    timeframe: str | None = None,
) -> dict[str, object]:
    if timeframe:
        raw = raw.copy()
        normalized = normalized.copy()
        raw["timeframe"] = timeframe.lower()
        normalized["timeframe"] = timeframe.lower()
    raw_paths = _write_frame_by_date(
        raw,
        layout=layout,
        layer="raw",
        kind=kind,
        exchange=exchange,
        market_type=market_type,
        symbol=symbol,
        timeframe=timeframe,
    )
    normalized_paths = _write_frame_by_date(
        normalized,
        layout=layout,
        layer="normalized",
        kind=kind,
        exchange=exchange,
        market_type=market_type,
        symbol=symbol,
        timeframe=timeframe,
    )
    return {
        "raw": raw_paths[-1] if raw_paths else None,
        "normalized": normalized_paths[-1] if normalized_paths else None,
        "raw_paths": raw_paths,
        "normalized_paths": normalized_paths,
        "rows": int(len(normalized)),
        "last_ts": pd.to_datetime(normalized["ts"], utc=True).max().isoformat(),
    }


@dataclass(slots=True)
class DataIngestionService:
    layout: DataLakeLayout

    def refresh_ohlcv(
        self,
        *,
        exchange: str,
        symbol: str,
        market_type: MarketType,
        timeframe: str = "1h",
        since: datetime | None = None,
        limit: int = 500,
        drop_incomplete: bool = False,
        client: CCXTDataClient | None = None,
    ) -> dict[str, object]:
        data_client = client or CCXTDataClient(exchange_name=exchange, market_type=market_type)
        raw = data_client.fetch_ohlcv(symbol=symbol, timeframe=timeframe, since=since, limit=limit)
        if drop_incomplete:
            raw = drop_incomplete_ohlcv(raw, timeframe=timeframe)
        if raw.empty:
            return {"raw": None, "normalized": None, "rows": 0, "last_ts": None}
        normalized = normalize_dataset(DatasetKind.OHLCV, raw)
        return _write_dataset_pair(
            layout=self.layout,
            raw=raw,
            normalized=normalized,
            kind=DatasetKind.OHLCV,
            exchange=exchange,
            market_type=market_type,
            symbol=symbol,
            timeframe=timeframe,
        )

    def refresh_funding_rates(
        self,
        *,
        exchange: str,
        symbol: str,
        since: datetime | None = None,
        limit: int = 500,
    ) -> dict[str, object]:
        client = CCXTDataClient(exchange_name=exchange, market_type=MarketType.PERP)
        raw = client.fetch_funding_rates(symbol=symbol, since=since, limit=limit)
        normalized = normalize_dataset(DatasetKind.FUNDING_RATES, raw)
        return _write_dataset_pair(
            layout=self.layout,
            raw=raw,
            normalized=normalized,
            kind=DatasetKind.FUNDING_RATES,
            exchange=exchange,
            market_type=MarketType.PERP,
            symbol=symbol,
        )

    def refresh_open_interest(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str = "1h",
        since: datetime | None = None,
        limit: int = 500,
    ) -> dict[str, object]:
        client = CCXTDataClient(exchange_name=exchange, market_type=MarketType.PERP)
        raw = client.fetch_open_interest(symbol=symbol, timeframe=timeframe, since=since, limit=limit)
        normalized = normalize_dataset(DatasetKind.OPEN_INTEREST, raw)
        return _write_dataset_pair(
            layout=self.layout,
            raw=raw,
            normalized=normalized,
            kind=DatasetKind.OPEN_INTEREST,
            exchange=exchange,
            market_type=MarketType.PERP,
            symbol=symbol,
            timeframe=timeframe,
        )

    def refresh_basis_or_premium(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str = "1h",
        since: datetime | None = None,
        limit: int = 500,
    ) -> dict[str, object]:
        client = CCXTDataClient(exchange_name=exchange, market_type=MarketType.PERP)
        raw = client.fetch_basis_or_premium(symbol=symbol, timeframe=timeframe, since=since, limit=limit)
        normalized = normalize_dataset(DatasetKind.BASIS, raw)
        return _write_dataset_pair(
            layout=self.layout,
            raw=raw,
            normalized=normalized,
            kind=DatasetKind.BASIS,
            exchange=exchange,
            market_type=MarketType.PERP,
            symbol=symbol,
            timeframe=timeframe,
        )

    def write_liquidation_events(
        self,
        frame: pd.DataFrame,
        *,
        exchange: str,
        symbol: str,
        market_type: MarketType = MarketType.PERP,
        timeframe: str | None = None,
    ) -> dict[str, object]:
        normalized = normalize_dataset(DatasetKind.LIQUIDATIONS, frame)
        return _write_dataset_pair(
            layout=self.layout,
            raw=frame,
            normalized=normalized,
            kind=DatasetKind.LIQUIDATIONS,
            exchange=exchange,
            market_type=market_type,
            symbol=symbol,
            timeframe=timeframe,
        )

    def refresh_historical_liquidations(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str = "4h",
        since: datetime | None = None,
        limit: int = 1000,
    ) -> dict[str, object]:
        client = CCXTDataClient(exchange_name=exchange, market_type=MarketType.PERP)
        raw = client.fetch_historical_liquidations(symbol=symbol, timeframe=timeframe, since=since, limit=limit)
        if raw.empty:
            return {"raw": None, "normalized": None, "rows": 0, "last_ts": None}
        return self.write_liquidation_events(
            raw,
            exchange=exchange,
            symbol=symbol,
            market_type=MarketType.PERP,
            timeframe=timeframe,
        )

    async def collect_liquidations(
        self,
        *,
        duration_seconds: float | None = None,
        max_events: int | None = None,
    ) -> pd.DataFrame:
        collector = BinanceLiquidationStreamCollector()
        return await collector.collect(duration_seconds=duration_seconds, max_events=max_events)
