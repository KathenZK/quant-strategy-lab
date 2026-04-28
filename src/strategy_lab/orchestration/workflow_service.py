from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import pandas as pd

from strategy_lab.backtest import CrossSectionalBacktester, PortfolioBacktester, compute_backtest_attribution
from strategy_lab.execution import PaperBroker, PaperTradingSession
from strategy_lab.features import FeatureBuilder
from strategy_lab.orchestration.models import StrategyWorkflowConfig
from strategy_lab.orchestration.panels import MultiFactorUniversePanels, UniversePanels, load_multi_factor_panels, load_universe_panels
from strategy_lab.portfolio import RiskManager
from strategy_lab.reporting import render_backtest_report, render_factor_report, render_paper_trading_report
from strategy_lab.research import FactorResearchLab
from strategy_lab.strategies import create_strategy


@dataclass(frozen=True, slots=True)
class PreparedWorkflow:
    signal_name: str
    signal_version: str
    panels: UniversePanels | MultiFactorUniversePanels
    signal_frame: pd.DataFrame
    target_weights: pd.DataFrame | None


@dataclass(frozen=True, slots=True)
class WorkflowExecutionResult:
    signal_name: str
    signal_version: str
    factor_report_path: str | None = None
    backtest_report_path: str | None = None
    paper_report_path: str | None = None
    structured_artifacts: dict[str, str] | None = None
    backtest_metrics: dict[str, float] | None = None
    backtest_attribution: dict[str, float | str | None] | None = None
    paper_summary: dict[str, float] | None = None


def _frame_with_ts(frame: pd.DataFrame | pd.Series, value_name: str | None = None) -> pd.DataFrame:
    if isinstance(frame, pd.Series):
        output = frame.rename(value_name or frame.name or "value").to_frame()
    else:
        output = frame.copy()
    index_name = output.index.name or "ts"
    return output.reset_index().rename(columns={index_name: "ts"})


def _build_trade_events(
    *,
    weights: pd.DataFrame,
    price_frame: pd.DataFrame,
    signal_frame: pd.DataFrame,
) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(
            columns=[
                "ts",
                "symbol",
                "side",
                "previous_weight",
                "target_weight",
                "delta_weight",
                "price",
                "signal",
                "reason",
            ]
        )

    aligned_prices = price_frame.reindex_like(weights)
    aligned_signals = signal_frame.reindex_like(weights)
    previous = weights.shift(1).fillna(0.0)
    delta = weights.fillna(0.0) - previous
    rows: list[dict[str, object]] = []
    for ts in delta.index:
        for symbol, delta_weight in delta.loc[ts].dropna().items():
            if abs(float(delta_weight)) < 1e-12:
                continue
            prior = float(previous.loc[ts, symbol])
            target = float(weights.loc[ts, symbol])
            if delta_weight > 0:
                reason = "increase_long" if target > 0 else "reduce_short"
                side = "buy"
            else:
                reason = "increase_short" if target < 0 else "reduce_long"
                side = "sell"
            rows.append(
                {
                    "ts": ts,
                    "symbol": symbol,
                    "side": side,
                    "previous_weight": prior,
                    "target_weight": target,
                    "delta_weight": float(delta_weight),
                    "price": float(aligned_prices.loc[ts, symbol]) if pd.notna(aligned_prices.loc[ts, symbol]) else None,
                    "signal": float(aligned_signals.loc[ts, symbol]) if pd.notna(aligned_signals.loc[ts, symbol]) else None,
                    "reason": reason,
                }
            )
    return pd.DataFrame(rows)


def _extended_backtest_metrics(
    *,
    backtest,
    price_frame: pd.DataFrame,
    trading_costs: pd.Series,
    gross_return_sum: float,
    benchmark_symbol: str | None,
) -> dict[str, float]:
    period_returns = backtest.period_returns.fillna(0.0)
    active_returns = period_returns[period_returns != 0.0]
    winners = active_returns[active_returns > 0.0]
    losers = active_returns[active_returns < 0.0]

    win_rate = float(len(winners) / len(active_returns)) if len(active_returns) else 0.0
    profit_loss_ratio = (
        float(winners.mean() / abs(losers.mean()))
        if len(winners) and len(losers) and losers.mean() != 0.0
        else 0.0
    )
    trading_cost_sum = float(trading_costs.fillna(0.0).sum())
    fee_ratio = trading_cost_sum / abs(float(gross_return_sum)) if gross_return_sum else 0.0

    benchmark_column = benchmark_symbol if benchmark_symbol in price_frame.columns else price_frame.columns[0] if len(price_frame.columns) else None
    buy_hold_return = 0.0
    if benchmark_column is not None:
        benchmark_price = price_frame[benchmark_column].dropna()
        if len(benchmark_price) >= 2 and benchmark_price.iloc[0] != 0.0:
            buy_hold_return = float(benchmark_price.iloc[-1] / benchmark_price.iloc[0] - 1.0)

    cumulative_return = float(backtest.metrics.get("cumulative_return", 0.0))
    return {
        "win_rate": win_rate,
        "profit_loss_ratio": profit_loss_ratio,
        "fee_ratio": fee_ratio,
        "trading_cost_sum": trading_cost_sum,
        "buy_hold_return": buy_hold_return,
        "excess_return_vs_buy_hold": cumulative_return - buy_hold_return,
    }


def _write_structured_artifacts(
    *,
    artifacts_dir: Path,
    signal_frame: pd.DataFrame,
    price_frame: pd.DataFrame,
    weights: pd.DataFrame | None,
    backtest,
    backtest_metrics: dict[str, float],
    backtest_attribution: dict[str, float | str | None],
) -> dict[str, str]:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    def _write_parquet(name: str, frame: pd.DataFrame | pd.Series, value_name: str | None = None) -> None:
        path = artifacts_dir / f"{name}.parquet"
        _frame_with_ts(frame, value_name=value_name).to_parquet(path, index=False)
        paths[name] = str(path)

    _write_parquet("signals", signal_frame)
    _write_parquet("prices", price_frame)
    if weights is not None:
        _write_parquet("weights", weights)
        trades = _build_trade_events(weights=weights, price_frame=price_frame, signal_frame=signal_frame)
        trade_path = artifacts_dir / "trades.parquet"
        trades.to_parquet(trade_path, index=False)
        paths["trades"] = str(trade_path)

    if backtest is not None:
        _write_parquet("equity_curve", backtest.equity_curve, value_name="equity")
        _write_parquet("period_returns", backtest.period_returns, value_name="returns")
        _write_parquet("turnover", backtest.turnover, value_name="turnover")
        _write_parquet("trading_costs", backtest.trading_costs, value_name="trading_costs")
        _write_parquet("funding_costs", backtest.funding_costs, value_name="funding_costs")

    metrics_path = artifacts_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "backtest_metrics": backtest_metrics,
                "backtest_attribution": backtest_attribution,
            },
            indent=2,
            sort_keys=True,
            default=str,
        ),
        encoding="utf-8",
    )
    paths["metrics"] = str(metrics_path)
    return paths


class WorkflowService:
    def __init__(self, builder: FeatureBuilder) -> None:
        self.builder = builder

    def required_factor_names(self, config: StrategyWorkflowConfig) -> list[str] | None:
        if not config.strategy.is_factor_strategy:
            strategy = create_strategy(config.strategy.strategy_type, config.strategy.strategy_params)
            return strategy.required_factors()
        if config.strategy.factor_name is not None:
            return [config.strategy.factor_name]
        return None

    def prepare(self, config: StrategyWorkflowConfig) -> PreparedWorkflow:
        if not config.strategy.is_factor_strategy:
            strategy = create_strategy(config.strategy.strategy_type, config.strategy.strategy_params)
            panels = load_multi_factor_panels(
                builder=self.builder,
                exchange=config.strategy.exchange,
                symbols=config.strategy.symbols,
                market_type=config.strategy.market_type,
                factor_names=strategy.required_factors(),
                benchmark_symbol=config.strategy.benchmark_symbol,
            )
            signal_frame = strategy.build_signal_frame(panels.factors)
            target_weights = strategy.build_weights(
                signal_frame,
                panels.liquidation_features,
                price_frame=panels.price,
                factors=panels.factors,
            )
            return PreparedWorkflow(
                signal_name=strategy.signal_name,
                signal_version=strategy.version(),
                panels=panels,
                signal_frame=signal_frame,
                target_weights=target_weights,
            )

        panels = load_universe_panels(
            builder=self.builder,
            exchange=config.strategy.exchange,
            symbols=config.strategy.symbols,
            market_type=config.strategy.market_type,
            factor_name=config.strategy.signal_name,
            benchmark_symbol=config.strategy.benchmark_symbol,
        )
        return PreparedWorkflow(
            signal_name=config.strategy.signal_name,
            signal_version=self.builder.registry.get(config.strategy.signal_name).version(),
            panels=panels,
            signal_frame=panels.factor,
            target_weights=None,
        )

    def run_backtest(self, config: StrategyWorkflowConfig, prepared: PreparedWorkflow):
        if prepared.target_weights is None:
            return CrossSectionalBacktester(assumptions=config.execution, risk_limits=config.risk).run(
                factor_frame=prepared.signal_frame,
                price_frame=prepared.panels.price,
                dollar_volume=prepared.panels.dollar_volume,
                funding_rate=prepared.panels.funding_rate,
            )
        return PortfolioBacktester(assumptions=config.execution, risk_limits=config.risk).run(
            target_weights=prepared.target_weights,
            price_frame=prepared.panels.price,
            dollar_volume=prepared.panels.dollar_volume,
            funding_rate=prepared.panels.funding_rate,
        )

    def execute(self, config: StrategyWorkflowConfig, *, run_dir: Path) -> WorkflowExecutionResult:
        prepared = self.prepare(config)
        factor_report_path: Path | None = None
        backtest_report_path: Path | None = None
        paper_report_path: Path | None = None
        backtest_metrics: dict[str, float] = {}
        backtest_attribution: dict[str, float | str | None] = {}
        paper_summary: dict[str, float] = {}
        backtest = None
        effective_weights = prepared.target_weights
        paper_target_weights = prepared.target_weights

        if config.run_factor_report:
            diagnostics = FactorResearchLab().evaluate(prepared.signal_frame, prepared.panels.price)
            report = render_factor_report(prepared.signal_name, diagnostics)
            factor_report_path = run_dir / "factor_report.md"
            factor_report_path.parent.mkdir(parents=True, exist_ok=True)
            factor_report_path.write_text(report, encoding="utf-8")

        if config.run_backtest:
            backtest = self.run_backtest(config, prepared)
            effective_weights = backtest.weights
            backtest_attribution = compute_backtest_attribution(
                weights=backtest.weights,
                price_frame=prepared.panels.price,
                funding_rate=prepared.panels.funding_rate,
                fee_bps=config.execution.fee_bps,
                slippage_bps=config.execution.slippage_bps,
            )
            backtest_metrics = {
                **backtest.metrics,
                **_extended_backtest_metrics(
                    backtest=backtest,
                    price_frame=prepared.panels.price,
                    trading_costs=backtest.trading_costs,
                    gross_return_sum=float(backtest_attribution.get("gross_return_sum") or 0.0),
                    benchmark_symbol=config.strategy.benchmark_symbol or (config.strategy.symbols[0] if config.strategy.symbols else None),
                ),
            }
            report = render_backtest_report(prepared.signal_name, backtest)
            backtest_report_path = run_dir / "backtest_report.md"
            backtest_report_path.parent.mkdir(parents=True, exist_ok=True)
            backtest_report_path.write_text(report, encoding="utf-8")

        if config.run_paper_trade and paper_target_weights is None:
            paper_target_weights = CrossSectionalBacktester(
                assumptions=config.execution,
                risk_limits=config.risk,
            ).build_weights(prepared.signal_frame)
            effective_weights = paper_target_weights

        structured_artifacts = _write_structured_artifacts(
            artifacts_dir=run_dir / "artifacts",
            signal_frame=prepared.signal_frame,
            price_frame=prepared.panels.price,
            weights=effective_weights,
            backtest=backtest,
            backtest_metrics=backtest_metrics,
            backtest_attribution=backtest_attribution,
        )

        if config.run_paper_trade:
            session = PaperTradingSession(
                broker=PaperBroker(
                    starting_cash=config.execution.starting_cash,
                    fee_bps=config.execution.fee_bps,
                    slippage_bps=config.execution.slippage_bps,
                ),
                risk_manager=RiskManager(config.risk),
            )
            paper = session.run(
                target_weights=paper_target_weights,
                price_frame=prepared.panels.price,
                dollar_volume=prepared.panels.dollar_volume,
                funding_rate=prepared.panels.funding_rate,
            )
            paper_summary = {
                "final_equity": float(paper.equity_curve.iloc[-1]) if not paper.equity_curve.empty else 0.0,
                "fill_count": float(len(paper.fills)),
                "funding_cashflow": float(paper.funding_cashflows.sum()) if not paper.funding_cashflows.empty else 0.0,
            }
            report = render_paper_trading_report(prepared.signal_name, paper)
            paper_report_path = run_dir / "paper_report.md"
            paper_report_path.parent.mkdir(parents=True, exist_ok=True)
            paper_report_path.write_text(report, encoding="utf-8")

        return WorkflowExecutionResult(
            signal_name=prepared.signal_name,
            signal_version=prepared.signal_version,
            factor_report_path=str(factor_report_path) if factor_report_path else None,
            backtest_report_path=str(backtest_report_path) if backtest_report_path else None,
            paper_report_path=str(paper_report_path) if paper_report_path else None,
            structured_artifacts=structured_artifacts,
            backtest_metrics=backtest_metrics,
            backtest_attribution=backtest_attribution,
            paper_summary=paper_summary,
        )
