from __future__ import annotations

from dataclasses import dataclass, field

from signal_lab.batches.models import WorkflowBatchEntry


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    name: str
    workflow_configs: list[str]
    description: str | None = None


ExperimentEntry = WorkflowBatchEntry


@dataclass(frozen=True, slots=True)
class ExperimentArtifacts:
    run_id: str
    report_path: str
    manifest_path: str
    entries: list[ExperimentEntry] = field(default_factory=list)
