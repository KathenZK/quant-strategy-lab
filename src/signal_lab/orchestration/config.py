from __future__ import annotations

from pathlib import Path

import yaml

from signal_lab.backtest import ExecutionAssumptions
from signal_lab.data import MarketType
from signal_lab.orchestration.models import RefreshOptions, ScheduleOptions, StrategyWorkflowConfig, StrategyWorkflowSpec
from signal_lab.portfolio import RiskLimits


def load_strategy_workflow(path: str | Path) -> StrategyWorkflowConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"strategy workflow config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    strategy = payload.get("strategy", {})
    refresh = payload.get("refresh", {})
    execution = payload.get("execution", {})
    risk = payload.get("risk", {})
    schedule = payload.get("schedule", {})
    workflow = payload.get("workflow", {})

    spec = StrategyWorkflowSpec(
        name=strategy["name"],
        exchange=strategy["exchange"],
        market_type=MarketType(strategy.get("market_type", "spot")),
        symbols=[symbol.upper() for symbol in strategy.get("symbols", [])],
        benchmark_symbol=strategy.get("benchmark_symbol", None),
        signal_type=strategy.get("signal_type", "factor"),
        factor=strategy.get("factor"),
        strategy_options=strategy.get("strategy_options", {}),
    )

    return StrategyWorkflowConfig(
        strategy=spec,
        refresh=RefreshOptions(
            enabled=refresh.get("enabled", True),
            incremental=refresh.get("incremental", True),
            include_derivatives=refresh.get("include_derivatives", True),
            timeframe=refresh.get("timeframe", "1h"),
            limit=refresh.get("limit", 500),
            since=refresh.get("since"),
            overlap_bars=refresh.get("overlap_bars", 50),
        ),
        execution=ExecutionAssumptions(
            fee_bps=execution.get("fee_bps", 5.0),
            slippage_bps=execution.get("slippage_bps", 2.0),
            starting_cash=execution.get("starting_cash", 100_000.0),
            max_abs_weight=execution.get("max_abs_weight", risk.get("max_abs_weight", 0.20)),
            max_gross_leverage=execution.get("max_gross_leverage", risk.get("max_gross_leverage", 1.0)),
            max_net_exposure=execution.get("max_net_exposure", risk.get("max_net_exposure", 1.0)),
            min_dollar_volume=execution.get("min_dollar_volume", risk.get("min_dollar_volume", 0.0)),
            max_funding_rate_abs=execution.get("max_funding_rate_abs", risk.get("max_funding_rate_abs")),
        ),
        risk=RiskLimits(
            max_abs_weight=risk.get("max_abs_weight", 0.20),
            max_gross_leverage=risk.get("max_gross_leverage", 1.0),
            max_net_exposure=risk.get("max_net_exposure", 1.0),
            min_dollar_volume=risk.get("min_dollar_volume", 0.0),
            max_funding_rate_abs=risk.get("max_funding_rate_abs"),
            max_drawdown=risk.get("max_drawdown"),
        ),
        schedule=ScheduleOptions(
            enabled=schedule.get("enabled", False),
            sleep_seconds=schedule.get("sleep_seconds", 0),
            max_runs=schedule.get("max_runs", 1),
        ),
        run_factor_report=workflow.get("run_factor_report", True),
        run_backtest=workflow.get("run_backtest", True),
        run_paper_trade=workflow.get("run_paper_trade", True),
    )
