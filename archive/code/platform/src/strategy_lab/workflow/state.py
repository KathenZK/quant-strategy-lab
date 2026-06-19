from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import json

import pandas as pd

from strategy_lab.data import DatasetKind, MarketType


def _parse_timeframe(value: str) -> pd.Timedelta:
    units = {"m": "min", "h": "h", "d": "d"}
    suffix = value[-1]
    amount = int(value[:-1])
    if suffix not in units:
        raise ValueError(f"unsupported timeframe: {value}")
    return pd.Timedelta(amount, unit=units[suffix])


SHARED_OWNER = "_shared_"
"""Sentinel owner used for legacy callers / shared-data refresh that is not tied
to a specific strategy. Strategy-driven callers should always pass their own
`strategy_name` so different strategies cannot fight over the same checkpoint."""


@dataclass(frozen=True, slots=True)
class RefreshCheckpoint:
    dataset: str
    exchange: str
    symbol: str
    market_type: str
    timeframe: str | None
    last_ts: str
    updated_at: str
    rows: int
    raw_path: str | None = None
    normalized_path: str | None = None
    owner: str = SHARED_OWNER


@dataclass(slots=True)
class IncrementalStateStore:
    root_dir: Path

    @property
    def state_path(self) -> Path:
        return self.root_dir / "_state" / "refresh_state.json"

    def _load_payload(self) -> dict[str, dict]:
        if not self.state_path.exists():
            return {}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _save_payload(self, payload: dict[str, dict]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _key(
        *,
        dataset: DatasetKind,
        exchange: str,
        symbol: str,
        market_type: MarketType,
        timeframe: str | None = None,
        owner: str = SHARED_OWNER,
    ) -> str:
        time_key = timeframe or "na"
        owner_key = (owner or SHARED_OWNER).strip() or SHARED_OWNER
        return f"{owner_key}|{dataset.value}|{exchange.lower()}|{market_type.value}|{symbol.upper()}|{time_key}"

    @staticmethod
    def _normalize_owner(owner: str | None) -> str:
        return (owner or SHARED_OWNER).strip() or SHARED_OWNER

    def get_checkpoint(
        self,
        *,
        dataset: DatasetKind,
        exchange: str,
        symbol: str,
        market_type: MarketType,
        timeframe: str | None = None,
        owner: str | None = None,
    ) -> RefreshCheckpoint | None:
        payload = self._load_payload()
        item = payload.get(
            self._key(
                dataset=dataset,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
                timeframe=timeframe,
                owner=self._normalize_owner(owner),
            )
        )
        return RefreshCheckpoint(**item) if item else None

    def resolve_since(
        self,
        *,
        dataset: DatasetKind,
        exchange: str,
        symbol: str,
        market_type: MarketType,
        timeframe: str | None = None,
        overlap_bars: int = 0,
        owner: str | None = None,
    ) -> datetime | None:
        checkpoint = self.get_checkpoint(
            dataset=dataset,
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            timeframe=timeframe,
            owner=owner,
        )
        if checkpoint is None:
            return None
        last_ts = pd.Timestamp(checkpoint.last_ts)
        if timeframe is None or overlap_bars <= 0:
            return last_ts.to_pydatetime()
        return (last_ts - (overlap_bars * _parse_timeframe(timeframe))).to_pydatetime()

    def update_checkpoint(
        self,
        *,
        dataset: DatasetKind,
        exchange: str,
        symbol: str,
        market_type: MarketType,
        last_ts: object,
        rows: int,
        raw_path: str | None,
        normalized_path: str | None,
        timeframe: str | None = None,
        owner: str | None = None,
    ) -> RefreshCheckpoint:
        normalized_owner = self._normalize_owner(owner)
        checkpoint = RefreshCheckpoint(
            dataset=dataset.value,
            exchange=exchange.lower(),
            symbol=symbol.upper(),
            market_type=market_type.value,
            timeframe=timeframe,
            last_ts=pd.to_datetime(last_ts, utc=True).isoformat(),
            updated_at=pd.Timestamp.now(tz="UTC").isoformat(),
            rows=rows,
            raw_path=raw_path,
            normalized_path=normalized_path,
            owner=normalized_owner,
        )
        payload = self._load_payload()
        payload[
            self._key(
                dataset=dataset,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
                timeframe=timeframe,
                owner=normalized_owner,
            )
        ] = asdict(checkpoint)
        self._save_payload(payload)
        return checkpoint

    def list_checkpoints(self, *, owner: str | None = None) -> list[RefreshCheckpoint]:
        payload = self._load_payload()
        records: list[RefreshCheckpoint] = []
        for raw in payload.values():
            data = dict(raw)
            data.setdefault("owner", SHARED_OWNER)
            records.append(RefreshCheckpoint(**data))
        if owner is None:
            return sorted(records, key=lambda c: (c.owner, c.dataset, c.exchange, c.symbol, c.timeframe or ""))
        normalized = self._normalize_owner(owner)
        return sorted(
            (c for c in records if c.owner == normalized),
            key=lambda c: (c.dataset, c.exchange, c.symbol, c.timeframe or ""),
        )
