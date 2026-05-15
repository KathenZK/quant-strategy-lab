from __future__ import annotations

from pathlib import Path

import yaml

from strategy_lab.data import MarketType
from strategy_lab.workflow.models import (
    ExecutionAssumptions,
    RefreshOptions,
    RiskLimits,
    ScheduleOptions,
    StrategyWorkflowConfig,
    StrategyWorkflowSpec,
    UniverseOptions,
)
from strategy_lab.strategies import create_strategy


def _first_defined(mapping: dict, *keys: str, default=None):
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def strategy_workflow_from_mapping(payload: dict) -> StrategyWorkflowConfig:
    strategy = payload.get("strategy", {})
    refresh = payload.get("refresh", {})
    universe = payload.get("universe", {})
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
        strategy_type=_first_defined(
            strategy, "strategy_type", "signal_type", default="factor"
        ),
        factor_name=_first_defined(strategy, "factor_name", "factor"),
        strategy_params=_first_defined(
            strategy, "strategy_params", "strategy_options", default={}
        ),
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
        universe=UniverseOptions(
            source=universe.get("source"),
            min_avg_dollar_volume=universe.get("min_avg_dollar_volume", 1_000_000.0),
            min_history_bars=universe.get("min_history_bars", 120),
            max_symbols=universe.get("max_symbols", 0),
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


def strategy_workflow_from_code(
    strategy_type: str,
    *,
    strategy_params: dict[str, object] | None = None,
    name: str | None = None,
    exchange: str = "binance",
    market_type: MarketType = MarketType.SPOT,
    symbols: list[str] | None = None,
    benchmark_symbol: str | None = "BTC/USDT",
    timeframe: str = "1h",
    use_local_universe: bool = False,
    min_avg_dollar_volume: float = 1_000_000.0,
    min_history_bars: int = 120,
    max_symbols: int = 0,
    run_factor_report: bool = False,
    run_backtest: bool = True,
    run_paper_trade: bool = False,
) -> StrategyWorkflowConfig:
    strategy = create_strategy(strategy_type, strategy_params or {})
    resolved_symbols = symbols or strategy.default_symbols(
        exchange=exchange, market_type=market_type
    )
    is_candle_count_short = strategy_type == "candle_count_short"
    allocation_cap = max(
        abs(float(getattr(getattr(strategy, "config", None), "long_allocation", 0.0))),
        abs(float(getattr(getattr(strategy, "config", None), "short_allocation", 0.0))),
    )
    max_abs_weight = (
        allocation_cap
        if is_candle_count_short
        else 1.0
        if strategy_type == "donchian_hold_72h"
        else 0.20
    )
    max_leverage = allocation_cap if is_candle_count_short else 1.0
    return StrategyWorkflowConfig(
        strategy=StrategyWorkflowSpec(
            name=name or f"{strategy_type}_{exchange}_{market_type.value}_{timeframe}",
            exchange=exchange,
            market_type=market_type,
            symbols=resolved_symbols,
            benchmark_symbol=None if is_candle_count_short else benchmark_symbol,
            strategy_type=strategy_type,
            strategy_params=strategy_params or {},
        ),
        refresh=RefreshOptions(
            enabled=is_candle_count_short,
            incremental=is_candle_count_short,
            include_derivatives=market_type == MarketType.PERP
            and not is_candle_count_short,
            timeframe=timeframe,
            limit=1000,
            overlap_bars=300 if is_candle_count_short else 0,
        ),
        universe=UniverseOptions(
            source="local_binance_spot" if use_local_universe else None,
            min_avg_dollar_volume=min_avg_dollar_volume,
            min_history_bars=min_history_bars,
            max_symbols=max_symbols,
        ),
        execution=ExecutionAssumptions(
            fee_bps=4.5 if is_candle_count_short else 10.0,
            slippage_bps=4.0
            if is_candle_count_short
            else 30.0
            if market_type == MarketType.SPOT
            else 10.0,
            starting_cash=100_000.0,
        ),
        risk=RiskLimits(
            max_abs_weight=max_abs_weight,
            max_gross_leverage=max_leverage,
            max_net_exposure=max_leverage,
            min_dollar_volume=0.0,
            max_drawdown=None if is_candle_count_short else 0.20,
        ),
        run_factor_report=run_factor_report,
        run_backtest=run_backtest,
        run_paper_trade=run_paper_trade,
        metadata={
            "config_source": "strategy_code",
            "strategy_type": strategy_type,
        },
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
