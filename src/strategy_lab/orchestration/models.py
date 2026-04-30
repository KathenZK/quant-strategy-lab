from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from strategy_lab.backtest import ExecutionAssumptions
from strategy_lab.data import MarketType
from strategy_lab.portfolio import RiskLimits


@dataclass(frozen=True, slots=True)
class RefreshOptions:
    enabled: bool = True
    incremental: bool = True
    include_derivatives: bool = True
    timeframe: str = "1h"
    limit: int = 500
    since: str | None = None
    overlap_bars: int = 50


@dataclass(frozen=True, slots=True)
class UniverseOptions:
    source: str | None = None
    min_avg_dollar_volume: float = 1_000_000.0
    min_history_bars: int = 120
    max_symbols: int = 0

    @property
    def enabled(self) -> bool:
        return bool(self.source)


@dataclass(frozen=True, slots=True)
class ScheduleOptions:
    enabled: bool = False
    sleep_seconds: int = 0
    max_runs: int = 1


@dataclass(frozen=True, slots=True)
class StrategyWorkflowSpec:
    name: str
    exchange: str
    market_type: MarketType
    symbols: list[str]
    benchmark_symbol: str | None = None
    strategy_type: str = "factor"
    factor_name: str | None = None
    strategy_params: dict[str, Any] = field(default_factory=dict)

    @property
    def is_factor_strategy(self) -> bool:
        return self.strategy_type == "factor"

    @property
    def signal_name(self) -> str:
        if self.is_factor_strategy:
            if self.factor_name is None:
                raise ValueError("factor strategy requires factor name")
            return self.factor_name
        return self.strategy_type


@dataclass(frozen=True, slots=True)
class StrategyWorkflowConfig:
    strategy: StrategyWorkflowSpec
    refresh: RefreshOptions = field(default_factory=RefreshOptions)
    universe: UniverseOptions = field(default_factory=UniverseOptions)
    execution: ExecutionAssumptions = field(default_factory=ExecutionAssumptions)
    risk: RiskLimits = field(default_factory=RiskLimits)
    schedule: ScheduleOptions = field(default_factory=ScheduleOptions)
    metadata: dict[str, Any] = field(default_factory=dict)
    run_factor_report: bool = True
    run_backtest: bool = True
    run_paper_trade: bool = True


@dataclass(frozen=True, slots=True)
class StrategyRunArtifacts:
    run_id: str
    factor_report_path: str | None = None
    backtest_report_path: str | None = None
    paper_report_path: str | None = None
    manifest_path: str | None = None
    backtest_metrics: dict[str, float] = field(default_factory=dict)
    paper_summary: dict[str, float] = field(default_factory=dict)
    backtest_attribution: dict[str, float | str | None] | None = None
