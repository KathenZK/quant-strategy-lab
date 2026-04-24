from __future__ import annotations

from pathlib import Path

import yaml

from signal_lab.batches import load_workflow_batch_config
from signal_lab.experiments.models import ExperimentConfig, ExperimentObjective, ExperimentVariant


def _resolve_config_path(config_path: Path, value: str | None) -> str | None:
    if not value:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = (config_path.parent / candidate).resolve()
    return str(candidate)


def _resolve_workflow_list(config_path: Path, values: list[str]) -> list[str]:
    resolved = []
    for value in values:
        path = _resolve_config_path(config_path, value)
        if path is not None:
            resolved.append(path)
    return resolved


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    experiment_payload = payload.get("experiment")
    if experiment_payload and ("base_workflow" in experiment_payload or "variants" in experiment_payload or "sweep" in experiment_payload):
        try:
            name = experiment_payload["name"]
        except KeyError as exc:
            raise KeyError("missing required key 'name' in experiment config") from exc

        objective_payload = experiment_payload.get("objective", {})
        variants = [
            ExperimentVariant(
                name=str(item["name"]),
                overrides=dict(item.get("overrides", {})),
            )
            for item in experiment_payload.get("variants", [])
        ]
        sweep = {
            str(key): list(value if isinstance(value, list) else [value])
            for key, value in dict(experiment_payload.get("sweep", {})).items()
        }
        return ExperimentConfig(
            name=name,
            description=experiment_payload.get("description"),
            workflow_configs=_resolve_workflow_list(config_path, experiment_payload.get("workflow_configs", [])),
            base_workflow=_resolve_config_path(config_path, experiment_payload.get("base_workflow")),
            variants=variants,
            sweep=sweep,
            objective=ExperimentObjective(
                metric=objective_payload.get("metric", "sharpe"),
                direction=objective_payload.get("direction", "max"),
            ),
            max_workers=int(experiment_payload.get("max_workers", 1)),
        )

    batch = load_workflow_batch_config(config_path, sections=("experiment", "batch"))
    return ExperimentConfig(
        name=batch.name,
        workflow_configs=batch.workflow_configs,
        description=batch.description,
        max_workers=batch.max_workers,
    )
