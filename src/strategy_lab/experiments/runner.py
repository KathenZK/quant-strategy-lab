from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
import hashlib
import json
import re

from strategy_lab.batches import WorkflowBatchRunner
from strategy_lab.experiments.models import ExperimentArtifacts, ExperimentConfig, ExperimentEntry, ExperimentVariant
from strategy_lab.experiments.registry import RunRegistry, RunRegistryEntry
from strategy_lab.orchestration import StrategyWorkflowConfig, load_strategy_workflow
from strategy_lab.orchestration.runner import StrategyRunner
from strategy_lab.reporting.experiments import render_experiment_report


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip()).strip("_")
    return slug or "variant"


def _variant_label_key(path: str) -> str:
    terminal = path.split(".")[-1]
    if terminal.endswith("_name"):
        return terminal.removesuffix("_name")
    if terminal.endswith("_type"):
        return terminal.removesuffix("_type")
    return terminal


def _config_hash(config: StrategyWorkflowConfig) -> str:
    encoded = json.dumps(asdict(config), sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _set_path(target, parts: list[str], value):
    if not parts:
        return value
    head, *tail = parts
    if isinstance(target, dict):
        updated = dict(target)
        updated[head] = _set_path(updated.get(head, {}), tail, value) if tail else value
        return updated
    if not is_dataclass(target):
        raise ValueError(f"cannot apply override through non-config object at: {head}")
    if not hasattr(target, head):
        raise ValueError(f"unknown override path segment: {head}")
    current = getattr(target, head)
    return replace(target, **{head: _set_path(current, tail, value) if tail else value})


def _apply_overrides(config: StrategyWorkflowConfig, overrides: dict[str, object]) -> StrategyWorkflowConfig:
    current = config
    for path, value in overrides.items():
        current = _set_path(current, str(path).split("."), value)
    return current


def _sweep_variants(sweep: dict[str, list[object]]) -> list[ExperimentVariant]:
    if not sweep:
        return []
    keys = list(sweep)
    variants = []
    for values in product(*(sweep[key] for key in keys)):
        overrides = dict(zip(keys, values, strict=True))
        label = "__".join(f"{_variant_label_key(key)}={value}" for key, value in overrides.items())
        variants.append(ExperimentVariant(name=_slug(label), overrides=overrides))
    return variants


def _build_variant_workflows(config: ExperimentConfig) -> list[StrategyWorkflowConfig]:
    workflows = [load_strategy_workflow(path) for path in config.workflow_configs]
    if not config.base_workflow:
        return workflows

    base = load_strategy_workflow(config.base_workflow)
    variants = list(config.variants) + _sweep_variants(config.sweep)
    if not variants:
        variants = [ExperimentVariant(name="base", overrides={})]

    for variant in variants:
        variant_id = _slug(variant.name)
        workflow = _apply_overrides(base, variant.overrides)
        if "strategy.name" not in variant.overrides:
            workflow = replace(
                workflow,
                strategy=replace(workflow.strategy, name=f"{base.strategy.name}__{variant_id}"),
            )
        metadata = dict(workflow.metadata)
        metadata.update(
            {
                "experiment_name": config.name,
                "variant_id": variant_id,
                "variant_name": variant.name,
                "base_workflow": config.base_workflow,
                "overrides": variant.overrides,
            }
        )
        workflow = replace(workflow, metadata=metadata)
        metadata["config_hash"] = _config_hash(workflow)
        workflows.append(replace(workflow, metadata=metadata))
    return workflows


def _rank_entries(entries: list[ExperimentEntry], metric: str, direction: str) -> list[ExperimentEntry]:
    reverse = direction != "min"
    missing_value = float("-inf") if reverse else float("inf")
    return sorted(entries, key=lambda item: item.backtest_metrics.get(metric, missing_value), reverse=reverse)


def _pick_winner(entries: list[ExperimentEntry], metric: str, direction: str) -> ExperimentEntry | None:
    ranked = _rank_entries(entries, metric, direction)
    return ranked[0] if ranked else None


class ExperimentRunner:
    def __init__(self, workspace_root: Path, app_config_path: Path | None = None) -> None:
        self.workspace_root = workspace_root
        self.app_config_path = app_config_path

    def _runtime(self) -> StrategyRunner:
        return self._batch_runner().create_strategy_runner()

    def _batch_runner(self) -> WorkflowBatchRunner:
        return WorkflowBatchRunner(workspace_root=self.workspace_root, app_config_path=self.app_config_path)

    def collect_entries(self, workflow_configs: list[str], *, max_workers: int = 1) -> list[ExperimentEntry]:
        return self._batch_runner().collect_entries(workflow_configs, max_workers=max_workers)

    def collect_entries_from_workflows(
        self,
        workflows: list[StrategyWorkflowConfig],
        *,
        runner: StrategyRunner | None = None,
        shared_refresh: bool = False,
        max_workers: int = 1,
    ) -> list[ExperimentEntry]:
        return self._batch_runner().collect_entries_from_workflows(
            workflows,
            runner=runner,
            shared_refresh=shared_refresh,
            max_workers=max_workers,
        )

    def run(self, config: ExperimentConfig) -> ExperimentArtifacts:
        workflows = _build_variant_workflows(config)
        if not workflows:
            raise ValueError("experiment requires at least one workflow config or base workflow")

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        batch_runner = self._batch_runner()
        runner = batch_runner.create_strategy_runner()
        experiment_dir = runner.layout.reports_dir / "experiments" / config.name / run_id
        experiment_dir.mkdir(parents=True, exist_ok=True)

        entries = batch_runner.collect_entries_from_workflows(
            workflows,
            runner=runner,
            max_workers=config.max_workers,
        )
        winner = _pick_winner(entries, config.objective.metric, config.objective.direction)
        report_path = experiment_dir / "experiment_report.md"
        report_path.write_text(
            render_experiment_report(
                config.name,
                entries,
                config.description,
                objective_metric=config.objective.metric,
                objective_direction=config.objective.direction,
                winner=winner,
            ),
            encoding="utf-8",
        )

        manifest_payload = {
            "run_id": run_id,
            "experiment": asdict(config),
            "app_config_path": str(self.app_config_path) if self.app_config_path else None,
            "entries": [asdict(entry) for entry in entries],
            "winner": asdict(winner) if winner is not None else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path = experiment_dir / "experiment_manifest.json"
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        RunRegistry(runner.layout.reports_dir, db_path=runner.layout.run_registry_db_path).append(
            RunRegistryEntry(
                kind="experiment_run",
                name=config.name,
                run_id=run_id,
                generated_at=str(manifest_payload["generated_at"]),
                manifest_path=str(manifest_path),
                app_config_path=str(self.app_config_path) if self.app_config_path else None,
                primary_report_path=str(report_path),
                child_manifest_paths=[entry.run_manifest_path for entry in entries if entry.run_manifest_path],
            ),
            manifest_payload=manifest_payload,
        )

        return ExperimentArtifacts(
            run_id=run_id,
            report_path=str(report_path),
            manifest_path=str(manifest_path),
            entries=entries,
            winner=winner,
        )
