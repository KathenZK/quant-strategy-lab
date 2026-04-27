from __future__ import annotations

from strategy_lab.comparison.models import StrategyComparisonEntry


def render_strategy_comparison_report(
    name: str,
    entries: list[StrategyComparisonEntry],
    description: str | None = None,
) -> str:
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
                f"- Strategy type: `{entry.strategy_type}`",
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
