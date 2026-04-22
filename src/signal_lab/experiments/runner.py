from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import json

from signal_lab.batches import WorkflowBatchRunner
from signal_lab.experiments.models import ExperimentArtifacts, ExperimentConfig, ExperimentEntry
from signal_lab.experiments.registry import RunRegistry, RunRegistryEntry
from signal_lab.orchestration import StrategyWorkflowConfig
from signal_lab.orchestration.runner import StrategyRunner


def _render_report(name: str, entries: list[ExperimentEntry], description: str | None = None) -> str:
    lines = [f"# Experiment Run: {name}", ""]
    if description:
        lines.extend([description, ""])

    lines.extend(
        [
            "## Summary",
            f"- Workflow count: `{len(entries)}`",
            "",
        ]
    )

    for entry in entries:
        metrics = entry.backtest_metrics
        paper = entry.paper_summary
        lines.extend(
            [
                f"## {entry.workflow_name}",
                f"- Strategy: `{entry.strategy_name}`",
                f"- Signal: `{entry.signal_name}`",
                f"- Signal type: `{entry.signal_type}`",
                f"- Signal version: `{entry.signal_version}`",
                f"- Run id: `{entry.run_id}`",
                f"- Cumulative return: {metrics.get('cumulative_return', 0.0):.4f}",
                f"- Sharpe: {metrics.get('sharpe', 0.0):.4f}",
                f"- Max drawdown: {metrics.get('max_drawdown', 0.0):.4f}",
                f"- Avg turnover: {metrics.get('avg_turnover', 0.0):.4f}",
                f"- Final equity: {paper.get('final_equity', 0.0):.4f}",
                f"- Fill count: {paper.get('fill_count', 0.0):.0f}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


class ExperimentRunner:
    def __init__(self, workspace_root: Path, app_config_path: Path | None = None) -> None:
        self.workspace_root = workspace_root
        self.app_config_path = app_config_path

    def _runtime(self) -> StrategyRunner:
        return self._batch_runner().create_strategy_runner()

    def _batch_runner(self) -> WorkflowBatchRunner:
        return WorkflowBatchRunner(workspace_root=self.workspace_root, app_config_path=self.app_config_path)

    def collect_entries(self, workflow_configs: list[str]) -> list[ExperimentEntry]:
        return self._batch_runner().collect_entries(workflow_configs)

    def collect_entries_from_workflows(
        self,
        workflows: list[StrategyWorkflowConfig],
        *,
        runner: StrategyRunner | None = None,
        shared_refresh: bool = False,
    ) -> list[ExperimentEntry]:
        return self._batch_runner().collect_entries_from_workflows(
            workflows,
            runner=runner,
            shared_refresh=shared_refresh,
        )

    def run(self, config: ExperimentConfig) -> ExperimentArtifacts:
        if not config.workflow_configs:
            raise ValueError("experiment requires at least one workflow config")

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        batch_runner = self._batch_runner()
        runner = batch_runner.create_strategy_runner()
        experiment_dir = runner.layout.reports_dir / "experiments" / config.name / run_id
        experiment_dir.mkdir(parents=True, exist_ok=True)

        workflows = batch_runner.load_workflows(config.workflow_configs)
        entries = batch_runner.collect_entries_from_workflows(workflows, runner=runner)
        report_path = experiment_dir / "experiment_report.md"
        report_path.write_text(_render_report(config.name, entries, config.description), encoding="utf-8")

        manifest_payload = {
            "run_id": run_id,
            "experiment": asdict(config),
            "app_config_path": str(self.app_config_path) if self.app_config_path else None,
            "entries": [asdict(entry) for entry in entries],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path = experiment_dir / "experiment_manifest.json"
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        RunRegistry(runner.layout.reports_dir).append(
            RunRegistryEntry(
                kind="experiment_run",
                name=config.name,
                run_id=run_id,
                generated_at=str(manifest_payload["generated_at"]),
                manifest_path=str(manifest_path),
                app_config_path=str(self.app_config_path) if self.app_config_path else None,
                primary_report_path=str(report_path),
                child_manifest_paths=[entry.run_manifest_path for entry in entries if entry.run_manifest_path],
            )
        )

        return ExperimentArtifacts(
            run_id=run_id,
            report_path=str(report_path),
            manifest_path=str(manifest_path),
            entries=entries,
        )
