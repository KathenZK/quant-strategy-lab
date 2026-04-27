from __future__ import annotations

from dataclasses import dataclass, field

from strategy_lab.batches.models import WorkflowBatchEntry


@dataclass(frozen=True, slots=True)
class ExperimentVariant:
    name: str
    overrides: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExperimentObjective:
    metric: str = "sharpe"
    direction: str = "max"


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    name: str
    workflow_configs: list[str] = field(default_factory=list)
    description: str | None = None
    base_workflow: str | None = None
    variants: list[ExperimentVariant] = field(default_factory=list)
    sweep: dict[str, list[object]] = field(default_factory=dict)
    objective: ExperimentObjective = field(default_factory=ExperimentObjective)
    max_workers: int = 1


ExperimentEntry = WorkflowBatchEntry


@dataclass(frozen=True, slots=True)
class ExperimentArtifacts:
    run_id: str
    report_path: str
    manifest_path: str
    entries: list[ExperimentEntry] = field(default_factory=list)
    winner: ExperimentEntry | None = None
