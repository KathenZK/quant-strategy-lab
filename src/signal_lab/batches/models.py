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
    max_workers: int = 1


@dataclass(frozen=True, slots=True)
class WorkflowBatchEntry:
    workflow_name: str
    strategy_name: str
    signal_name: str
    strategy_type: str
    signal_version: str
    run_id: str
    variant_id: str | None = None
    backtest_metrics: dict[str, float] = field(default_factory=dict)
    backtest_attribution: dict[str, float | str | None] = field(default_factory=dict)
    paper_summary: dict[str, float] = field(default_factory=dict)
    factor_report_path: str | None = None
    backtest_report_path: str | None = None
    paper_report_path: str | None = None
    run_manifest_path: str | None = None
    structured_artifact_paths: dict[str, str] = field(default_factory=dict)
