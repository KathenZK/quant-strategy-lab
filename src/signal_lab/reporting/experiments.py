from __future__ import annotations

from signal_lab.experiments.models import ExperimentEntry


def render_experiment_report(
    name: str,
    entries: list[ExperimentEntry],
    description: str | None = None,
    *,
    objective_metric: str = "sharpe",
    objective_direction: str = "max",
    winner: ExperimentEntry | None = None,
) -> str:
    lines = [f"# Experiment Run: {name}", ""]
    if description:
        lines.extend([description, ""])

    lines.extend(
        [
            "## Summary",
            f"- Workflow count: `{len(entries)}`",
            f"- Objective: `{objective_metric}` ({objective_direction})",
        ]
    )
    if winner is not None:
        lines.append(
            f"- Winner: `{winner.strategy_name}` ({objective_metric}={winner.backtest_metrics.get(objective_metric, 0.0):.4f})"
        )
    lines.append("")

    ranked = sorted(
        entries,
        key=lambda item: item.backtest_metrics.get(
            objective_metric,
            float("-inf") if objective_direction != "min" else float("inf"),
        ),
        reverse=objective_direction != "min",
    )
    for entry in ranked:
        metrics = entry.backtest_metrics
        paper = entry.paper_summary
        lines.extend(
            [
                f"## {entry.workflow_name}",
                f"- Variant: `{entry.variant_id or '-'}`",
                f"- Strategy: `{entry.strategy_name}`",
                f"- Signal: `{entry.signal_name}`",
                f"- Strategy type: `{entry.strategy_type}`",
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
