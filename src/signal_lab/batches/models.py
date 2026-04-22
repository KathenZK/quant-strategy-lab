from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class BatchRunMode(StrEnum):
    EXPERIMENT = "experiment"
    COMPARISON = "comparison"


@dataclass(frozen=True, slots=True)
class WorkflowBatchConfig:
    name: str
    workflow_configs: list[str]
    description: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowBatchEntry:
    workflow_name: str
    strategy_name: str
    signal_name: str
    signal_type: str
    signal_version: str
    run_id: str
    backtest_metrics: dict[str, float] = field(default_factory=dict)
    backtest_attribution: dict[str, float | str | None] = field(default_factory=dict)
    paper_summary: dict[str, float] = field(default_factory=dict)
    factor_report_path: str | None = None
    backtest_report_path: str | None = None
    paper_report_path: str | None = None
    run_manifest_path: str | None = None
