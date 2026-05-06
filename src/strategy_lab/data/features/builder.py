from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from strategy_lab.data import DuckDBWarehouse, MarketType
from strategy_lab.data.factors import FactorRegistry, compute_factor_bundle, default_registry
from strategy_lab.data.features.manifest import FactorArtifactManifest
from strategy_lab.data.features.store import FeatureStore


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
        timeframe: str | None = None,
        benchmark_symbol: str | None = None,
    ) -> pd.DataFrame:
        frame = self.warehouse.merged_market_frame(
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            timeframe=timeframe,
        )
        if frame.empty:
            return frame

        enriched = frame.copy().sort_values("ts").reset_index(drop=True)
        perp_fill_columns = (
            "funding_rate",
            "next_funding_ts",
            "open_interest",
            "open_interest_value",
            "basis",
            "basis_rate",
            "annualized_basis",
            "futures_price",
            "index_price",
            "mark_price",
            "premium_index",
        )
        for column in perp_fill_columns:
            if column in enriched.columns:
                enriched[column] = enriched[column].ffill()

        if "vwap" not in enriched.columns:
            enriched["vwap"] = (enriched["high"] + enriched["low"] + enriched["close"]) / 3.0
        if benchmark_symbol:
            benchmark = self.warehouse.merged_market_frame(
                exchange=exchange,
                symbol=benchmark_symbol,
                market_type=market_type,
                timeframe=timeframe,
            )
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
        timeframe: str | None = None,
        benchmark_symbol: str | None = None,
        factor_names: list[str] | None = None,
        market_frame: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        frame = (
            market_frame.copy()
            if market_frame is not None
            else self.load_symbol_frame(
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
                timeframe=timeframe,
                benchmark_symbol=benchmark_symbol,
            )
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
        cached, missing = self._load_cached_factor_bundle(
            frame,
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            timeframe=timeframe,
            factor_names=selected,
        )
        if not missing:
            return cached

        computed = compute_factor_bundle(frame, self.registry, factor_names=missing)
        if cached.empty:
            return computed
        merge_keys = [column for column in ("ts", "exchange", "symbol", "market_type", "timeframe") if column in cached.columns and column in computed.columns]
        merged = cached.merge(computed[[*merge_keys, *missing]], on=merge_keys, how="left")
        return merged

    def _load_cached_factor_bundle(
        self,
        frame: pd.DataFrame,
        *,
        exchange: str,
        symbol: str,
        market_type: MarketType,
        timeframe: str | None,
        factor_names: list[str],
    ) -> tuple[pd.DataFrame, list[str]]:
        base_columns = [column for column in ("ts", "exchange", "symbol", "market_type", "timeframe") if column in frame.columns]
        if not base_columns:
            return pd.DataFrame(), factor_names
        cached_bundle = frame[base_columns].copy()
        frame_ts = set(pd.to_datetime(frame["ts"], utc=True)) if "ts" in frame.columns else set()
        missing: list[str] = []

        for factor_name in factor_names:
            factor = self.registry.get(factor_name)
            cached = self.store.load_factor_frame(
                factor_name,
                exchange=exchange,
                market_type=market_type.value,
                symbol=symbol,
                timeframe=timeframe,
                factor_version=factor.version(),
            )
            if cached.empty or factor_name not in cached.columns or not self._covers_frame(cached, frame_ts):
                missing.append(factor_name)
                continue
            merge_keys = [column for column in base_columns if column in cached.columns]
            cached_bundle = cached_bundle.merge(cached[[*merge_keys, factor_name]], on=merge_keys, how="left")

        return cached_bundle, missing

    @staticmethod
    def _covers_frame(cached: pd.DataFrame, frame_ts: set[pd.Timestamp]) -> bool:
        if not frame_ts or "ts" not in cached.columns:
            return False
        cached_ts = set(pd.to_datetime(cached["ts"], utc=True))
        return frame_ts.issubset(cached_ts)

    def persist_bundle(
        self,
        factor_bundle: pd.DataFrame,
        *,
        exchange: str,
        symbol: str,
        market_type: MarketType,
        timeframe: str | None = None,
        benchmark_symbol: str | None = None,
    ) -> dict[str, dict[str, str]]:
        saved: dict[str, dict[str, str]] = {}
        base_columns = tuple(column for column in ("ts", "exchange", "symbol", "market_type", "timeframe") if column in factor_bundle.columns)
        for column in factor_bundle.columns:
            if column in base_columns:
                continue
            factor = self.registry.get(column)
            frame = factor_bundle[[*base_columns, column]]
            path = self.store.write_factor_frame(
                column,
                frame,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type.value,
                timeframe=timeframe,
                factor_version=factor.version(),
            )
            manifest = FactorArtifactManifest.create(
                factor_name=column,
                factor_version=factor.version(),
                factor_category=factor.metadata.category,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type.value,
                timeframe=timeframe,
                frame=frame,
                feature_path=path,
                benchmark_symbol=benchmark_symbol,
            )
            manifest_path = self.store.write_manifest(manifest)
            saved[column] = {
                "feature_path": str(path),
                "manifest_path": str(manifest_path),
                "factor_version": factor.version(),
            }
        return saved
