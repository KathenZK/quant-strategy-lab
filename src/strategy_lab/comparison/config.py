from __future__ import annotations

from pathlib import Path

from strategy_lab.batches import load_workflow_batch_config
from strategy_lab.comparison.models import StrategyComparisonConfig


def load_strategy_comparison(path: str | Path) -> StrategyComparisonConfig:
    batch = load_workflow_batch_config(path, sections=("comparison", "batch"))
    return StrategyComparisonConfig(
        name=batch.name,
        workflow_configs=batch.workflow_configs,
        description=batch.description,
    )
