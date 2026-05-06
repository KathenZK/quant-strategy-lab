from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class StrategyComparisonConfig:
    name: str
    workflow_configs: list[str]
    description: str | None = None


@dataclass(frozen=True, slots=True)
class StrategyComparisonEntry:
    strategy_name: str
    signal_name: str
    strategy_type: str
    signal_version: str
    metrics: dict[str, float]
    attribution: dict[str, float | str | None]
    backtest_report_path: str | None = None


@dataclass(frozen=True, slots=True)
class StrategyComparisonArtifacts:
    run_id: str
    report_path: str
    manifest_path: str
    entries: list[StrategyComparisonEntry] = field(default_factory=list)
