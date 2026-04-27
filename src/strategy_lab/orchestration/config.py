from __future__ import annotations

from pathlib import Path

import yaml

from strategy_lab.backtest import ExecutionAssumptions
from strategy_lab.data import MarketType
from strategy_lab.orchestration.models import RefreshOptions, ScheduleOptions, StrategyWorkflowConfig, StrategyWorkflowSpec
from strategy_lab.portfolio import RiskLimits


def _first_defined(mapping: dict, *keys: str, default=None):
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def strategy_workflow_from_mapping(payload: dict) -> StrategyWorkflowConfig:
    strategy = payload.get("strategy", {})
    refresh = payload.get("refresh", {})
    execution = payload.get("execution", {})
    risk = payload.get("risk", {})
    schedule = payload.get("schedule", {})
    workflow = payload.get("workflow", {})
    metadata = payload.get("metadata", {})

    spec = StrategyWorkflowSpec(
        name=strategy["name"],
        exchange=strategy["exchange"],
        market_type=MarketType(strategy.get("market_type", "spot")),
        symbols=[symbol.upper() for symbol in strategy.get("symbols", [])],
        benchmark_symbol=strategy.get("benchmark_symbol", None),
        strategy_type=_first_defined(strategy, "strategy_type", "signal_type", default="factor"),
        factor_name=_first_defined(strategy, "factor_name", "factor"),
        strategy_params=_first_defined(strategy, "strategy_params", "strategy_options", default={}),
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
        metadata=metadata,
        run_factor_report=workflow.get("run_factor_report", True),
        run_backtest=workflow.get("run_backtest", True),
        run_paper_trade=workflow.get("run_paper_trade", True),
    )


def load_strategy_workflow(path: str | Path) -> StrategyWorkflowConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"strategy workflow config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    return strategy_workflow_from_mapping(payload)


def load_strategy_workflow_text(workflow_yaml: str) -> StrategyWorkflowConfig:
    payload = yaml.safe_load(workflow_yaml) or {}
    if not isinstance(payload, dict):
        raise ValueError("strategy workflow YAML must contain a mapping")
    return strategy_workflow_from_mapping(payload)
