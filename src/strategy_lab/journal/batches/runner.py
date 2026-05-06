from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
import json

from strategy_lab.journal.batches.models import WorkflowBatchEntry
from strategy_lab.settings import load_settings
from strategy_lab.data.features import FeatureBuilder, FeatureStore
from strategy_lab.workflow import StrategyWorkflowConfig, load_strategy_workflow
from strategy_lab.workflow import StrategyRunner


def _entry_from_artifacts(workflow: StrategyWorkflowConfig, artifacts) -> WorkflowBatchEntry:
    manifest_path = Path(artifacts.manifest_path) if artifacts.manifest_path else None
    manifest_payload = {}
    if manifest_path is not None:
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    metadata = dict(manifest_payload.get("metadata", {}))
    return WorkflowBatchEntry(
        workflow_name=workflow.strategy.name,
        strategy_name=workflow.strategy.name,
        signal_name=str(manifest_payload.get("signal_name", workflow.strategy.signal_name)),
        strategy_type=str(manifest_payload.get("strategy_type", workflow.strategy.strategy_type)),
        signal_version=str(manifest_payload.get("signal_version", "")),
        run_id=str(manifest_payload.get("run_id", artifacts.run_id)),
        variant_id=metadata.get("variant_id"),
        backtest_metrics=dict(manifest_payload.get("backtest_metrics", {})),
        backtest_attribution=dict(manifest_payload.get("backtest_attribution", {})),
        paper_summary=dict(manifest_payload.get("paper_summary", {})),
        factor_report_path=artifacts.factor_report_path,
        backtest_report_path=artifacts.backtest_report_path,
        paper_report_path=artifacts.paper_report_path,
        run_manifest_path=artifacts.manifest_path,
        structured_artifact_paths=dict(manifest_payload.get("structured_artifacts", {})),
    )


def _run_workflow_entry(
    workspace_root: Path,
    app_config_path: Path | None,
    workflow: StrategyWorkflowConfig,
) -> WorkflowBatchEntry:
    runner = WorkflowBatchRunner(workspace_root=workspace_root, app_config_path=app_config_path).create_strategy_runner()
    return _entry_from_artifacts(workflow, runner.run(workflow))


def _supports_parallel_execution(workflows: list[StrategyWorkflowConfig]) -> bool:
    # Refresh writes shared raw/normalized partitions, so keep those runs serial.
    return all(not workflow.refresh.enabled for workflow in workflows)


class WorkflowBatchRunner:
    def __init__(self, workspace_root: Path, app_config_path: Path | None = None) -> None:
        self.workspace_root = workspace_root
        self.app_config_path = app_config_path

    def create_strategy_runner(self) -> StrategyRunner:
        settings = load_settings(self.app_config_path)
        from strategy_lab.data import DataLakeLayout, DuckDBWarehouse

        layout = DataLakeLayout.from_settings(settings)
        layout.ensure_directories()
        builder = FeatureBuilder(
            warehouse=DuckDBWarehouse(layout),
            store=FeatureStore(layout),
        )
        return StrategyRunner(layout=layout, builder=builder)

    def load_workflows(self, workflow_configs: list[str]) -> list[StrategyWorkflowConfig]:
        return [load_strategy_workflow(path) for path in workflow_configs]

    def collect_entries_from_workflows(
        self,
        workflows: list[StrategyWorkflowConfig],
        *,
        runner: StrategyRunner | None = None,
        shared_refresh: bool = False,
        max_workers: int = 1,
    ) -> list[WorkflowBatchEntry]:
        if not workflows:
            raise ValueError("workflow batch requires at least one workflow config")

        runner = runner or self.create_strategy_runner()
        effective_workflows = workflows
        if shared_refresh and workflows:
            reference = workflows[0]
            if reference.refresh.enabled:
                runner.refresh_data(reference)
            effective_workflows = [
                replace(workflow, refresh=replace(workflow.refresh, enabled=False))
                for workflow in workflows
            ]

        entries: list[WorkflowBatchEntry] = []
        worker_count = max(1, int(max_workers))
        if worker_count == 1 or len(effective_workflows) == 1 or not _supports_parallel_execution(effective_workflows):
            for workflow in effective_workflows:
                artifacts = runner.run(workflow)
                entries.append(_entry_from_artifacts(workflow, artifacts))
            return entries

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(_run_workflow_entry, self.workspace_root, self.app_config_path, workflow): index
                for index, workflow in enumerate(effective_workflows)
            }
            ordered: list[WorkflowBatchEntry | None] = [None] * len(effective_workflows)
            for future in as_completed(future_map):
                ordered[future_map[future]] = future.result()

        entries = [entry for entry in ordered if entry is not None]
        return entries

    def collect_entries(self, workflow_configs: list[str], *, max_workers: int = 1) -> list[WorkflowBatchEntry]:
        workflows = self.load_workflows(workflow_configs)
        return self.collect_entries_from_workflows(workflows, max_workers=max_workers)
