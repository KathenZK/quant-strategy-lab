from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from signal_lab.batches.config import load_workflow_batch_config
from signal_lab.batches.models import BatchRunMode, WorkflowBatchConfig

if TYPE_CHECKING:
    from signal_lab.comparison.models import StrategyComparisonArtifacts
    from signal_lab.experiments.models import ExperimentArtifacts


def load_batch_for_mode(path: str | Path, mode: BatchRunMode) -> WorkflowBatchConfig:
    if mode == BatchRunMode.COMPARISON:
        return load_workflow_batch_config(path, sections=("comparison", "batch"))
    if mode == BatchRunMode.EXPERIMENT:
        return load_workflow_batch_config(path, sections=("experiment", "batch"))
    raise ValueError(f"unsupported batch run mode: {mode}")


def run_workflow_batch(
    mode: BatchRunMode,
    batch_config: WorkflowBatchConfig,
    *,
    workspace_root: Path,
    app_config_path: Path | None = None,
) -> "ExperimentArtifacts | StrategyComparisonArtifacts":
    if mode == BatchRunMode.EXPERIMENT:
        from signal_lab.experiments.models import ExperimentConfig
        from signal_lab.experiments.runner import ExperimentRunner

        return ExperimentRunner(workspace_root=workspace_root, app_config_path=app_config_path).run(
            ExperimentConfig(
                name=batch_config.name,
                workflow_configs=batch_config.workflow_configs,
                description=batch_config.description,
            )
        )

    if mode == BatchRunMode.COMPARISON:
        from signal_lab.comparison.models import StrategyComparisonConfig
        from signal_lab.comparison.runner import StrategyComparisonRunner

        return StrategyComparisonRunner(workspace_root=workspace_root, app_config_path=app_config_path).compare(
            StrategyComparisonConfig(
                name=batch_config.name,
                workflow_configs=batch_config.workflow_configs,
                description=batch_config.description,
            )
        )

    raise ValueError(f"unsupported batch run mode: {mode}")
