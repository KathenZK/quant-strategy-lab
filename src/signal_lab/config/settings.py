from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(slots=True)
class StorageConfig:
    root_dir: Path
    raw_dir: Path
    normalized_dir: Path
    features_dir: Path
    reports_dir: Path


@dataclass(slots=True)
class ExchangeConfig:
    name: str
    enabled: bool = True
    market_types: list[str] = field(default_factory=lambda: ["spot", "perp"])
    quote_assets: list[str] = field(default_factory=lambda: ["USDT"])


@dataclass(slots=True)
class ResearchConfig:
    bar_frequencies: list[str] = field(default_factory=lambda: ["1h", "4h", "1d"])
    benchmark_symbols: list[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    universe_filters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AppSettings:
    name: str
    timezone: str
    storage: StorageConfig
    exchanges: list[ExchangeConfig]
    research: ResearchConfig


def default_settings(project_root: Path | None = None) -> AppSettings:
    root = project_root or _project_root()
    return AppSettings(
        name="quant-strategy-lab",
        timezone="UTC",
        storage=StorageConfig(
            root_dir=root / "data",
            raw_dir=root / "data" / "raw",
            normalized_dir=root / "data" / "normalized",
            features_dir=root / "data" / "features",
            reports_dir=root / "reports",
        ),
        exchanges=[
            ExchangeConfig(name="binance", quote_assets=["USDT", "USDC"]),
            ExchangeConfig(name="okx", quote_assets=["USDT", "USDC"]),
        ],
        research=ResearchConfig(
            universe_filters={
                "min_avg_dollar_volume": 1_000_000,
                "exclude_stablecoins": True,
            }
        ),
    )


def load_settings(path: str | Path | None = None) -> AppSettings:
    defaults = default_settings()
    if path is None:
        return defaults

    settings_path = Path(path)
    if not settings_path.exists():
        raise FileNotFoundError(f"settings file not found: {settings_path}")

    with settings_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    project = payload.get("project", {})
    storage = payload.get("storage", {})
    exchanges = payload.get("exchanges", [])
    research = payload.get("research", {})

    return AppSettings(
        name=project.get("name", defaults.name),
        timezone=project.get("timezone", defaults.timezone),
        storage=StorageConfig(
            root_dir=Path(storage.get("root_dir", defaults.storage.root_dir)),
            raw_dir=Path(storage.get("raw_dir", defaults.storage.raw_dir)),
            normalized_dir=Path(storage.get("normalized_dir", defaults.storage.normalized_dir)),
            features_dir=Path(storage.get("features_dir", defaults.storage.features_dir)),
            reports_dir=Path(storage.get("reports_dir", defaults.storage.reports_dir)),
        ),
        exchanges=[
            ExchangeConfig(
                name=item["name"],
                enabled=item.get("enabled", True),
                market_types=item.get("market_types", ["spot", "perp"]),
                quote_assets=item.get("quote_assets", ["USDT"]),
            )
            for item in (exchanges or [{"name": exchange.name} for exchange in defaults.exchanges])
        ],
        research=ResearchConfig(
            bar_frequencies=research.get("bar_frequencies", defaults.research.bar_frequencies),
            benchmark_symbols=research.get("benchmark_symbols", defaults.research.benchmark_symbols),
            universe_filters=research.get("universe_filters", defaults.research.universe_filters),
        ),
    )
