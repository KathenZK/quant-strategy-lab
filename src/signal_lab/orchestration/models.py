from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from signal_lab.backtest import ExecutionAssumptions
from signal_lab.data import MarketType
from signal_lab.portfolio import RiskLimits


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
    signal_type: str = "factor"
    factor: str | None = None
    strategy_options: dict[str, Any] = field(default_factory=dict)

    @property
    def signal_name(self) -> str:
        if self.signal_type == "factor":
            if self.factor is None:
                raise ValueError("factor strategy requires factor name")
            return self.factor
        return self.name


@dataclass(frozen=True, slots=True)
class StrategyWorkflowConfig:
    strategy: StrategyWorkflowSpec
    refresh: RefreshOptions = field(default_factory=RefreshOptions)
    execution: ExecutionAssumptions = field(default_factory=ExecutionAssumptions)
    risk: RiskLimits = field(default_factory=RiskLimits)
    schedule: ScheduleOptions = field(default_factory=ScheduleOptions)
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
    backtest_attribution: dict[str, float | str | None] | None = None
