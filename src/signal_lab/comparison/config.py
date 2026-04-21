from __future__ import annotations

from pathlib import Path

import yaml

from signal_lab.comparison.models import StrategyComparisonConfig


def load_strategy_comparison(path: str | Path) -> StrategyComparisonConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"strategy comparison config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    comparison = payload.get("comparison", {})
    workflow_configs = []
    for item in comparison.get("workflow_configs", []):
        candidate = Path(item)
        if not candidate.is_absolute():
            candidate = (config_path.parent / candidate).resolve()
        workflow_configs.append(str(candidate))

    return StrategyComparisonConfig(
        name=comparison["name"],
        workflow_configs=workflow_configs,
        description=comparison.get("description"),
    )
