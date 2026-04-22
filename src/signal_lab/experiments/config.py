from __future__ import annotations

from pathlib import Path

from signal_lab.batches import load_workflow_batch_config
from signal_lab.experiments.models import ExperimentConfig


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    batch = load_workflow_batch_config(path, sections=("experiment", "batch"))
    return ExperimentConfig(
        name=batch.name,
        workflow_configs=batch.workflow_configs,
        description=batch.description,
    )
