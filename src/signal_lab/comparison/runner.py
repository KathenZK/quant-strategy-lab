from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json

from signal_lab.batches import WorkflowBatchRunner
from signal_lab.comparison.models import StrategyComparisonArtifacts, StrategyComparisonConfig, StrategyComparisonEntry
from signal_lab.experiments.registry import RunRegistry, RunRegistryEntry
from signal_lab.orchestration import load_strategy_workflow


def _render_report(name: str, entries: list[StrategyComparisonEntry], description: str | None = None) -> str:
    by_return = sorted(entries, key=lambda item: item.metrics.get("cumulative_return", 0.0), reverse=True)
    by_sharpe = sorted(entries, key=lambda item: item.metrics.get("sharpe", 0.0), reverse=True)
    by_drawdown = sorted(entries, key=lambda item: item.metrics.get("max_drawdown", -1.0), reverse=True)

    lines = [f"# Strategy Comparison: {name}", ""]
    if description:
        lines.extend([description, ""])

    lines.extend(
        [
            "## Summary",
            f"- Best cumulative return: `{by_return[0].strategy_name}` ({by_return[0].metrics.get('cumulative_return', 0.0):.4f})",
            f"- Best sharpe: `{by_sharpe[0].strategy_name}` ({by_sharpe[0].metrics.get('sharpe', 0.0):.4f})",
            f"- Lowest drawdown: `{by_drawdown[0].strategy_name}` ({by_drawdown[0].metrics.get('max_drawdown', 0.0):.4f})",
            "",
        ]
    )

    for entry in entries:
        metrics = entry.metrics
        attribution = entry.attribution
        lines.extend(
            [
                f"## {entry.strategy_name}",
                f"- Signal: `{entry.signal_name}`",
                f"- Signal version: `{entry.signal_version}`",
                f"- Cumulative return: {metrics.get('cumulative_return', 0.0):.4f}",
                f"- Annualized return: {metrics.get('annualized_return', 0.0):.4f}",
                f"- Sharpe: {metrics.get('sharpe', 0.0):.4f}",
                f"- Max drawdown: {metrics.get('max_drawdown', 0.0):.4f}",
                f"- Avg turnover: {metrics.get('avg_turnover', 0.0):.4f}",
                f"- Gross return sum: {attribution.get('gross_return_sum', 0.0):.4f}",
                f"- Trading cost sum: {attribution.get('trading_cost_sum', 0.0):.4f}",
                f"- Funding cost sum: {attribution.get('funding_cost_sum', 0.0):.4f}",
                f"- Active period ratio: {attribution.get('active_period_ratio', 0.0):.4f}",
                f"- Avg gross exposure: {attribution.get('avg_gross_exposure', 0.0):.4f}",
                f"- Avg net exposure: {attribution.get('avg_net_exposure', 0.0):.4f}",
                f"- Top symbol: `{attribution.get('top_symbol')}` ({float(attribution.get('top_symbol_contribution', 0.0)):.4f})",
                f"- Worst symbol: `{attribution.get('worst_symbol')}` ({float(attribution.get('worst_symbol_contribution', 0.0)):.4f})",
                f"- Largest trading cost symbol: `{attribution.get('top_trading_cost_symbol')}` ({float(attribution.get('top_trading_cost', 0.0)):.4f})",
                f"- Largest funding cost symbol: `{attribution.get('top_funding_cost_symbol')}` ({float(attribution.get('top_funding_cost', 0.0)):.4f})",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


@dataclass(slots=True)
class StrategyComparisonRunner:
    workspace_root: Path
    app_config_path: Path | None = None

    def compare(self, config: StrategyComparisonConfig) -> StrategyComparisonArtifacts:
        if len(config.workflow_configs) < 2:
            raise ValueError("strategy comparison requires at least two workflow configs")

        workflow_configs = [load_strategy_workflow(path) for path in config.workflow_configs]
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

        batch_runner = WorkflowBatchRunner(workspace_root=self.workspace_root, app_config_path=self.app_config_path)
        runtime_runner = batch_runner.create_strategy_runner()
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
                    signal_type=source.signal_type,
                    signal_version=source.signal_version,
                    metrics=source.backtest_metrics,
                    attribution=source.backtest_attribution,
                    backtest_report_path=copied_report_path,
                )
            )

        report_path = comparison_dir / "comparison_report.md"
        report_path.write_text(_render_report(config.name, entries, config.description), encoding="utf-8")

        manifest_payload = {
            "run_id": run_id,
            "comparison": asdict(config),
            "app_config_path": str(self.app_config_path) if self.app_config_path else None,
            "entries": [
                {
                    "strategy_name": entry.strategy_name,
                    "signal_name": entry.signal_name,
                    "signal_type": entry.signal_type,
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
        RunRegistry(runtime_runner.layout.reports_dir).append(
            RunRegistryEntry(
                kind="comparison_run",
                name=config.name,
                run_id=run_id,
                generated_at=str(manifest_payload["generated_at"]),
                manifest_path=str(manifest_path),
                app_config_path=str(self.app_config_path) if self.app_config_path else None,
                primary_report_path=str(report_path),
                child_manifest_paths=[entry.run_manifest_path for entry in source_entries if entry.run_manifest_path],
            )
        )

        return StrategyComparisonArtifacts(
            run_id=run_id,
            report_path=str(report_path),
            manifest_path=str(manifest_path),
            entries=entries,
        )
