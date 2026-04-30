from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json

from strategy_lab.batches import WorkflowBatchRunner
from strategy_lab.comparison.models import StrategyComparisonArtifacts, StrategyComparisonConfig, StrategyComparisonEntry
from strategy_lab.experiments.registry import RunRegistry, RunRegistryEntry
from strategy_lab.orchestration import load_strategy_workflow
from strategy_lab.reporting.comparison import render_strategy_comparison_report


@dataclass(slots=True)
class StrategyComparisonRunner:
    workspace_root: Path
    app_config_path: Path | None = None

    def compare(self, config: StrategyComparisonConfig) -> StrategyComparisonArtifacts:
        if len(config.workflow_configs) < 2:
            raise ValueError("strategy comparison requires at least two workflow configs")

        batch_runner = WorkflowBatchRunner(workspace_root=self.workspace_root, app_config_path=self.app_config_path)
        runtime_runner = batch_runner.create_strategy_runner()
        workflow_configs = [
            runtime_runner.workflow_service.with_resolved_symbols(load_strategy_workflow(path))
            for path in config.workflow_configs
        ]
        reference = workflow_configs[0]

        for current in workflow_configs[1:]:
            if current.strategy.exchange != reference.strategy.exchange:
                raise ValueError("all compared strategies must share the same exchange")
            if current.strategy.market_type != reference.strategy.market_type:
                raise ValueError("all compared strategies must share the same market type")
            if current.strategy.symbols != reference.strategy.symbols:
                raise ValueError("all compared strategies must share the same symbol universe")
            if asdict(current.execution) != asdict(reference.execution):
                raise ValueError("all compared strategies must share the same execution assumptions")

        source_entries = batch_runner.collect_entries_from_workflows(
            workflow_configs,
            runner=runtime_runner,
            shared_refresh=True,
        )
        entries: list[StrategyComparisonEntry] = []
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        comparison_dir = runtime_runner.layout.reports_dir / "comparisons" / config.name / run_id
        comparison_dir.mkdir(parents=True, exist_ok=True)

        for source in source_entries:
            copied_report_path: str | None = None
            if source.backtest_report_path:
                backtest_report_path = comparison_dir / f"{source.strategy_name}.backtest.md"
                backtest_report_path.write_text(
                    Path(source.backtest_report_path).read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
                copied_report_path = str(backtest_report_path)
            entries.append(
                StrategyComparisonEntry(
                    strategy_name=source.strategy_name,
                    signal_name=source.signal_name,
                    strategy_type=source.strategy_type,
                    signal_version=source.signal_version,
                    metrics=source.backtest_metrics,
                    attribution=source.backtest_attribution,
                    backtest_report_path=copied_report_path,
                )
            )

        report_path = comparison_dir / "comparison_report.md"
        report_path.write_text(render_strategy_comparison_report(config.name, entries, config.description), encoding="utf-8")

        manifest_payload = {
            "run_id": run_id,
            "comparison": asdict(config),
            "app_config_path": str(self.app_config_path) if self.app_config_path else None,
            "entries": [
                {
                    "strategy_name": entry.strategy_name,
                    "signal_name": entry.signal_name,
                    "strategy_type": entry.strategy_type,
                    "signal_version": entry.signal_version,
                    "metrics": entry.metrics,
                    "attribution": entry.attribution,
                    "backtest_report_path": entry.backtest_report_path,
                }
                for entry in entries
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path = comparison_dir / "comparison_manifest.json"
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        RunRegistry(runtime_runner.layout.reports_dir, db_path=runtime_runner.layout.run_registry_db_path).append(
            RunRegistryEntry(
                kind="comparison_run",
                name=config.name,
                run_id=run_id,
                generated_at=str(manifest_payload["generated_at"]),
                manifest_path=str(manifest_path),
                app_config_path=str(self.app_config_path) if self.app_config_path else None,
                primary_report_path=str(report_path),
                child_manifest_paths=[entry.run_manifest_path for entry in source_entries if entry.run_manifest_path],
            ),
            manifest_payload=manifest_payload,
        )

        return StrategyComparisonArtifacts(
            run_id=run_id,
            report_path=str(report_path),
            manifest_path=str(manifest_path),
            entries=entries,
        )
