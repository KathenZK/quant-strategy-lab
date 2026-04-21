from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json

import pandas as pd

from signal_lab.backtest import CrossSectionalBacktester, PortfolioBacktester
from signal_lab.comparison.models import StrategyComparisonArtifacts, StrategyComparisonConfig, StrategyComparisonEntry
from signal_lab.config import load_settings
from signal_lab.features import FeatureBuilder, FeatureStore
from signal_lab.orchestration import load_strategy_workflow
from signal_lab.orchestration.runner import StrategyRunner


def _compute_attribution(
    *,
    weights: pd.DataFrame,
    price_frame: pd.DataFrame,
    funding_rate: pd.DataFrame | None,
    fee_bps: float,
    slippage_bps: float,
) -> dict[str, float | str | None]:
    executed = weights.shift(1).fillna(0.0)
    asset_returns = price_frame.pct_change().fillna(0.0)
    gross_contribution = executed * asset_returns
    contribution_by_symbol = gross_contribution.sum(axis=0).sort_values(ascending=False)

    turnover_by_symbol = weights.diff().abs().fillna(weights.abs()).sum(axis=0)
    trading_cost_by_symbol = turnover_by_symbol * ((fee_bps + slippage_bps) / 10_000.0)

    funding_cost_by_symbol = pd.Series(0.0, index=weights.columns)
    if funding_rate is not None:
        aligned_funding = funding_rate.reindex_like(price_frame).fillna(0.0)
        funding_cost_by_symbol = -(executed * aligned_funding).sum(axis=0)

    gross_exposure = weights.abs().sum(axis=1)
    net_exposure = weights.sum(axis=1)

    def _pick(series: pd.Series, *, descending: bool) -> tuple[str | None, float]:
        if series.empty:
            return None, 0.0
        ranked = series.sort_values(ascending=not descending)
        return str(ranked.index[0]), float(ranked.iloc[0])

    top_symbol, top_contribution = _pick(contribution_by_symbol, descending=True)
    worst_symbol, worst_contribution = _pick(contribution_by_symbol, descending=False)
    top_trading_symbol, top_trading_cost = _pick(trading_cost_by_symbol, descending=True)
    top_funding_symbol, top_funding_cost = _pick(funding_cost_by_symbol, descending=True)

    return {
        "gross_return_sum": float(gross_contribution.sum(axis=1).sum()),
        "trading_cost_sum": float(trading_cost_by_symbol.sum()),
        "funding_cost_sum": float(funding_cost_by_symbol.sum()),
        "active_period_ratio": float((gross_exposure > 0).mean()),
        "avg_gross_exposure": float(gross_exposure.mean()),
        "avg_net_exposure": float(net_exposure.mean()),
        "avg_long_count": float((weights > 0).sum(axis=1).mean()),
        "avg_short_count": float((weights < 0).sum(axis=1).mean()),
        "top_symbol": top_symbol,
        "top_symbol_contribution": top_contribution,
        "worst_symbol": worst_symbol,
        "worst_symbol_contribution": worst_contribution,
        "top_trading_cost_symbol": top_trading_symbol,
        "top_trading_cost": top_trading_cost,
        "top_funding_cost_symbol": top_funding_symbol,
        "top_funding_cost": top_funding_cost,
    }


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

    def _runtime(self) -> tuple[StrategyRunner, FeatureBuilder]:
        settings = load_settings(self.app_config_path)
        from signal_lab.data import DataLakeLayout, DuckDBWarehouse

        layout = DataLakeLayout.from_settings(settings)
        layout.ensure_directories()
        builder = FeatureBuilder(
            warehouse=DuckDBWarehouse(layout),
            store=FeatureStore(layout),
        )
        return StrategyRunner(layout=layout, builder=builder), builder

    def compare(self, config: StrategyComparisonConfig) -> StrategyComparisonArtifacts:
        if len(config.workflow_configs) < 2:
            raise ValueError("strategy comparison requires at least two workflow configs")

        runner, _ = self._runtime()
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

        if reference.refresh.enabled:
            runner.refresh_data(reference)

        entries: list[StrategyComparisonEntry] = []
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        comparison_dir = runner.layout.reports_dir / "comparisons" / config.name / run_id
        comparison_dir.mkdir(parents=True, exist_ok=True)

        for workflow in workflow_configs:
            runner.build_features(workflow)
            signal_name, signal_version, panels, signal_frame, target_weights = runner._prepare_signal_inputs(workflow)

            if target_weights is None:
                backtest = CrossSectionalBacktester(assumptions=workflow.execution).run(
                    factor_frame=signal_frame,
                    price_frame=panels.price,
                    dollar_volume=panels.dollar_volume,
                    funding_rate=panels.funding_rate,
                )
            else:
                backtest = PortfolioBacktester(assumptions=workflow.execution).run(
                    target_weights=target_weights,
                    price_frame=panels.price,
                    dollar_volume=panels.dollar_volume,
                    funding_rate=panels.funding_rate,
                )

            backtest_report_path = comparison_dir / f"{workflow.strategy.name}.backtest.md"
            from signal_lab.reporting import render_backtest_report

            backtest_report_path.write_text(render_backtest_report(signal_name, backtest), encoding="utf-8")
            attribution = _compute_attribution(
                weights=backtest.weights,
                price_frame=panels.price,
                funding_rate=panels.funding_rate,
                fee_bps=workflow.execution.fee_bps,
                slippage_bps=workflow.execution.slippage_bps,
            )
            entries.append(
                StrategyComparisonEntry(
                    strategy_name=workflow.strategy.name,
                    signal_name=signal_name,
                    signal_type=workflow.strategy.signal_type,
                    signal_version=signal_version,
                    metrics=backtest.metrics,
                    attribution=attribution,
                    backtest_report_path=str(backtest_report_path),
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

        return StrategyComparisonArtifacts(
            run_id=run_id,
            report_path=str(report_path),
            manifest_path=str(manifest_path),
            entries=entries,
        )
