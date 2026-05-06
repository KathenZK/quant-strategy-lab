from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from strategy_lab.journal.batches.config import load_workflow_batch_config
from strategy_lab.journal.batches.models import BatchRunMode, WorkflowBatchConfig

if TYPE_CHECKING:
    from strategy_lab.journal.comparison.models import StrategyComparisonArtifacts
    from strategy_lab.journal.models import ExperimentArtifacts


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
        from strategy_lab.journal.models import ExperimentConfig
        from strategy_lab.journal.runner import ExperimentRunner

        return ExperimentRunner(workspace_root=workspace_root, app_config_path=app_config_path).run(
            ExperimentConfig(
                name=batch_config.name,
                workflow_configs=batch_config.workflow_configs,
                description=batch_config.description,
            )
        )

    if mode == BatchRunMode.COMPARISON:
        from strategy_lab.journal.comparison.models import StrategyComparisonConfig
        from strategy_lab.journal.comparison.runner import StrategyComparisonRunner

        return StrategyComparisonRunner(workspace_root=workspace_root, app_config_path=app_config_path).compare(
            StrategyComparisonConfig(
                name=batch_config.name,
                workflow_configs=batch_config.workflow_configs,
                description=batch_config.description,
            )
        )

    raise ValueError(f"unsupported batch run mode: {mode}")
