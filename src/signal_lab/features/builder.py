from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from signal_lab.data import DuckDBWarehouse, MarketType
from signal_lab.factors import FactorRegistry, compute_factor_bundle, default_registry
from signal_lab.features.store import FeatureStore


@dataclass(slots=True)
class FeatureBuilder:
    warehouse: DuckDBWarehouse
    store: FeatureStore
    registry: FactorRegistry = field(default_factory=default_registry)

    def load_symbol_frame(
        self,
        *,
        exchange: str,
        symbol: str,
        market_type: MarketType,
        benchmark_symbol: str | None = None,
    ) -> pd.DataFrame:
        frame = self.warehouse.merged_market_frame(exchange=exchange, symbol=symbol, market_type=market_type)
        if frame.empty:
            return frame

        enriched = frame.copy()
        enriched["vwap"] = (enriched["high"] + enriched["low"] + enriched["close"]) / 3.0
        if benchmark_symbol:
            benchmark = self.warehouse.merged_market_frame(exchange=exchange, symbol=benchmark_symbol, market_type=market_type)
            if not benchmark.empty:
                enriched = enriched.merge(
                    benchmark[["ts", "close"]].rename(columns={"close": "benchmark_close"}),
                    on="ts",
                    how="left",
                )
        return enriched

    def build_symbol_features(
        self,
        *,
        exchange: str,
        symbol: str,
        market_type: MarketType,
        benchmark_symbol: str | None = None,
        factor_names: list[str] | None = None,
    ) -> pd.DataFrame:
        frame = self.load_symbol_frame(
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            benchmark_symbol=benchmark_symbol,
        )
        if frame.empty:
            return frame

        selected = factor_names
        if selected is None:
            selected = [
                metadata.name
                for metadata in self.registry.list_metadata()
                if all(column in frame.columns for column in metadata.inputs)
            ]
        return compute_factor_bundle(frame, self.registry, factor_names=selected)

    def persist_bundle(self, factor_bundle: pd.DataFrame) -> dict[str, str]:
        saved: dict[str, str] = {}
        base_columns = {"ts", "exchange", "symbol", "market_type"}
        for column in factor_bundle.columns:
            if column in base_columns:
                continue
            path = self.store.write_factor_frame(column, factor_bundle[[*base_columns, column]])
            saved[column] = str(path)
        return saved
