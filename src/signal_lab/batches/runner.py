from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json

from signal_lab.batches.models import WorkflowBatchEntry
from signal_lab.config import load_settings
from signal_lab.features import FeatureBuilder, FeatureStore
from signal_lab.orchestration import StrategyWorkflowConfig, load_strategy_workflow
from signal_lab.orchestration.runner import StrategyRunner


class WorkflowBatchRunner:
    def __init__(self, workspace_root: Path, app_config_path: Path | None = None) -> None:
        self.workspace_root = workspace_root
        self.app_config_path = app_config_path

    def create_strategy_runner(self) -> StrategyRunner:
        settings = load_settings(self.app_config_path)
        from signal_lab.data import DataLakeLayout, DuckDBWarehouse

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
        for workflow in effective_workflows:
            artifacts = runner.run(workflow)

            manifest_path = Path(artifacts.manifest_path) if artifacts.manifest_path else None
            manifest_payload = {}
            if manifest_path is not None:
                manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

            entries.append(
                WorkflowBatchEntry(
                    workflow_name=workflow.strategy.name,
                    strategy_name=workflow.strategy.name,
                    signal_name=str(manifest_payload.get("signal_name", workflow.strategy.signal_name)),
                    signal_type=str(manifest_payload.get("signal_type", workflow.strategy.signal_type)),
                    signal_version=str(manifest_payload.get("signal_version", "")),
                    run_id=str(manifest_payload.get("run_id", artifacts.run_id)),
                    backtest_metrics=dict(manifest_payload.get("backtest_metrics", {})),
                    backtest_attribution=dict(manifest_payload.get("backtest_attribution", {})),
                    paper_summary=dict(manifest_payload.get("paper_summary", {})),
                    factor_report_path=artifacts.factor_report_path,
                    backtest_report_path=artifacts.backtest_report_path,
                    paper_report_path=artifacts.paper_report_path,
                    run_manifest_path=artifacts.manifest_path,
                )
            )
        return entries

    def collect_entries(self, workflow_configs: list[str]) -> list[WorkflowBatchEntry]:
        workflows = self.load_workflows(workflow_configs)
        return self.collect_entries_from_workflows(workflows)
