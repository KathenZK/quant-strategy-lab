from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import typer

from signal_lab.batches import BatchRunMode
from signal_lab.batches.service import load_batch_for_mode, run_workflow_batch
from signal_lab.config import load_settings
from signal_lab.backtest import CrossSectionalBacktester, ExecutionAssumptions
from signal_lab.data import DataIngestionService, DataLakeLayout, DuckDBWarehouse, MarketType
from signal_lab.execution import PaperBroker, PaperTradingSession
from signal_lab.experiments import RunRegistry
from signal_lab.factors import default_registry
from signal_lab.features import FeatureBuilder, FeatureStore
from signal_lab.orchestration import IncrementalStateStore, StrategyRunner, load_strategy_workflow, load_universe_panels
from signal_lab.portfolio import RiskLimits, RiskManager
from signal_lab.reporting import render_backtest_report, render_factor_report, render_paper_trading_report
from signal_lab.research import FactorResearchLab
from signal_lab.scenarios import seed_crowding_mvp_data, seed_shared_comparison_mvp_data, seed_trend_mvp_data

app = typer.Typer(add_completion=False, help="Quant Strategy Lab research platform CLI.")


def _parse_since(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _parse_symbols(value: str) -> list[str]:
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def _runtime(config: Path | None) -> tuple[DataLakeLayout, DuckDBWarehouse, FeatureBuilder]:
    settings = load_settings(config)
    lake = DataLakeLayout.from_settings(settings)
    lake.ensure_directories()
    warehouse = DuckDBWarehouse(lake)
    builder = FeatureBuilder(warehouse=warehouse, store=FeatureStore(lake), registry=default_registry())
    return lake, warehouse, builder


def _run_batch_command(mode: BatchRunMode, batch_config: Path, config: Path | None) -> None:
    batch = load_batch_for_mode(batch_config, mode)
    artifacts = run_workflow_batch(
        mode,
        batch,
        workspace_root=Path.cwd(),
        app_config_path=config,
    )
    typer.echo(f"run_id: {artifacts.run_id}")
    typer.echo(f"report: {artifacts.report_path}")
    typer.echo(f"manifest: {artifacts.manifest_path}")


@app.command()
def layout(config: Path | None = typer.Option(None, "--config", "-c", help="Optional YAML config path.")) -> None:
    """Print data lake directories."""
    lake, _, _ = _runtime(config)
    for key, value in lake.summary().items():
        typer.echo(f"{key}: {value}")


@app.command()
def init_dirs(config: Path | None = typer.Option(None, "--config", "-c", help="Optional YAML config path.")) -> None:
    """Create data lake directories."""
    lake, _, _ = _runtime(config)
    lake.ensure_directories()
    typer.echo("created data lake directories")


@app.command()
def factors() -> None:
    """List built-in factors and metadata."""
    registry = default_registry()
    for metadata in registry.list_metadata():
        typer.echo(
            f"{metadata.name}\t{metadata.category}\tlookback={metadata.lookback}\tmarkets={','.join(metadata.market_types)}"
        )


@app.command()
def refresh_symbol(
    exchange: str = typer.Option(..., "--exchange", help="Exchange id, for example: binance"),
    symbol: str = typer.Option(..., "--symbol", help="Trading symbol, for example: BTC/USDT"),
    timeframe: str = typer.Option("1h", "--timeframe", help="Bar timeframe."),
    market_type: str = typer.Option("spot", "--market-type", help="spot or perp"),
    limit: int = typer.Option(500, "--limit", min=1, help="How many bars to fetch."),
    since: str | None = typer.Option(None, "--since", help="ISO-8601 datetime in UTC."),
    include_derivatives: bool = typer.Option(True, "--include-derivatives/--ohlcv-only", help="Fetch funding and open interest for perp markets."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional YAML config path."),
) -> None:
    """Fetch market data and store both raw and normalized datasets."""
    lake, _, _ = _runtime(config)
    market = MarketType(market_type)
    service = DataIngestionService(lake)
    since_dt = _parse_since(since)

    ohlcv_paths = service.refresh_ohlcv(
        exchange=exchange,
        symbol=symbol,
        market_type=market,
        timeframe=timeframe,
        since=since_dt,
        limit=limit,
    )
    typer.echo(f"ohlcv raw={ohlcv_paths['raw']}")
    typer.echo(f"ohlcv normalized={ohlcv_paths['normalized']}")

    if market == MarketType.PERP and include_derivatives:
        for name, action in (
            ("funding", lambda: service.refresh_funding_rates(exchange=exchange, symbol=symbol, since=since_dt, limit=limit)),
            ("open_interest", lambda: service.refresh_open_interest(exchange=exchange, symbol=symbol, timeframe=timeframe, since=since_dt, limit=limit)),
            ("basis_or_premium", lambda: service.refresh_basis_or_premium(exchange=exchange, symbol=symbol, timeframe=timeframe, since=since_dt, limit=limit)),
            ("historical_liquidations", lambda: service.refresh_historical_liquidations(exchange=exchange, symbol=symbol, timeframe='4h', since=since_dt, limit=1000)),
        ):
            try:
                paths = action()
                if not paths.get("rows"):
                    typer.echo(f"{name} skipped: no rows returned")
                    continue
                typer.echo(f"{name} raw={paths['raw']}")
                typer.echo(f"{name} normalized={paths['normalized']}")
            except NotImplementedError as exc:
                typer.echo(f"{name} skipped: {exc}")


@app.command()
def collect_liquidations(
    duration_seconds: int = typer.Option(60, "--duration-seconds", min=1, help="How long to collect liquidation events."),
    max_events: int | None = typer.Option(None, "--max-events", min=1, help="Optional maximum number of websocket messages."),
    symbol: str | None = typer.Option(None, "--symbol", help="Optional symbol filter, for example BTC/USDT:USDT."),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Collect Binance liquidation stream events and store them into the lake."""
    lake, _, _ = _runtime(config)
    service = DataIngestionService(lake)
    frame = asyncio.run(service.collect_liquidations(duration_seconds=duration_seconds, max_events=max_events))
    if frame.empty:
        typer.echo("no liquidation events collected")
        return

    working = frame
    if symbol:
        working = working[working["symbol"] == symbol.upper()]
        if working.empty:
            typer.echo("no events matched the requested symbol")
            return

    typer.echo(f"collected {len(working)} liquidation events")
    for current_symbol, group in working.groupby("symbol"):
        result = service.write_liquidation_events(
            group.reset_index(drop=True),
            exchange=str(group["exchange"].iloc[0]),
            symbol=current_symbol,
            market_type=MarketType(str(group["market_type"].iloc[0])),
        )
        typer.echo(f"{current_symbol} raw={result['raw']}")
        typer.echo(f"{current_symbol} normalized={result['normalized']}")


@app.command()
def build_features(
    exchange: str = typer.Option(..., "--exchange"),
    symbol: str = typer.Option(..., "--symbol"),
    market_type: str = typer.Option("spot", "--market-type"),
    benchmark_symbol: str | None = typer.Option(None, "--benchmark-symbol"),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Build and persist feature values for a single symbol."""
    _, _, builder = _runtime(config)
    bundle = builder.build_symbol_features(
        exchange=exchange,
        symbol=symbol,
        market_type=MarketType(market_type),
        benchmark_symbol=benchmark_symbol,
    )
    if bundle.empty:
        raise typer.BadParameter("no normalized data found for the requested symbol")
    saved = builder.persist_bundle(
        bundle,
        exchange=exchange,
        symbol=symbol,
        market_type=MarketType(market_type),
        benchmark_symbol=benchmark_symbol,
    )
    typer.echo(f"saved {len(saved)} factor files")
    for name, path in sorted(saved.items()):
        typer.echo(f"{name}: {path['feature_path']} ({path['factor_version']})")


@app.command()
def factor_report(
    exchange: str = typer.Option(..., "--exchange"),
    symbols: str = typer.Option(..., "--symbols", help="Comma-separated trading symbols."),
    factor_name: str = typer.Option(..., "--factor"),
    market_type: str = typer.Option("spot", "--market-type"),
    benchmark_symbol: str | None = typer.Option(None, "--benchmark-symbol"),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Generate a markdown factor report for a symbol universe."""
    lake, _, builder = _runtime(config)
    panels = load_universe_panels(
        builder=builder,
        exchange=exchange,
        symbols=_parse_symbols(symbols),
        market_type=MarketType(market_type),
        factor_name=factor_name,
        benchmark_symbol=benchmark_symbol,
    )
    diagnostics = FactorResearchLab().evaluate(panels.factor, panels.price)
    report = render_factor_report(factor_name, diagnostics)
    report_path = lake.reports_dir / "factors" / f"{factor_name}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    typer.echo(str(report_path))


@app.command()
def backtest_factor(
    exchange: str = typer.Option(..., "--exchange"),
    symbols: str = typer.Option(..., "--symbols"),
    factor_name: str = typer.Option(..., "--factor"),
    market_type: str = typer.Option("spot", "--market-type"),
    benchmark_symbol: str | None = typer.Option(None, "--benchmark-symbol"),
    fee_bps: float = typer.Option(5.0, "--fee-bps"),
    slippage_bps: float = typer.Option(2.0, "--slippage-bps"),
    max_abs_weight: float = typer.Option(0.20, "--max-abs-weight"),
    max_gross_leverage: float = typer.Option(1.0, "--max-gross-leverage"),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Run a cross-sectional factor backtest and save a report."""
    lake, _, builder = _runtime(config)
    panels = load_universe_panels(
        builder=builder,
        exchange=exchange,
        symbols=_parse_symbols(symbols),
        market_type=MarketType(market_type),
        factor_name=factor_name,
        benchmark_symbol=benchmark_symbol,
    )
    backtester = CrossSectionalBacktester(
        assumptions=ExecutionAssumptions(
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            max_abs_weight=max_abs_weight,
            max_gross_leverage=max_gross_leverage,
        )
    )
    result = backtester.run(
        factor_frame=panels.factor,
        price_frame=panels.price,
        dollar_volume=panels.dollar_volume,
        funding_rate=panels.funding_rate,
    )
    report = render_backtest_report(factor_name, result)
    report_path = lake.reports_dir / "backtests" / f"{factor_name}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    typer.echo(str(report_path))
    for key, value in result.metrics.items():
        typer.echo(f"{key}: {value:.6f}")


@app.command()
def paper_trade(
    exchange: str = typer.Option(..., "--exchange"),
    symbols: str = typer.Option(..., "--symbols"),
    factor_name: str = typer.Option(..., "--factor"),
    market_type: str = typer.Option("spot", "--market-type"),
    benchmark_symbol: str | None = typer.Option(None, "--benchmark-symbol"),
    starting_cash: float = typer.Option(100_000.0, "--starting-cash"),
    fee_bps: float = typer.Option(5.0, "--fee-bps"),
    slippage_bps: float = typer.Option(2.0, "--slippage-bps"),
    max_abs_weight: float = typer.Option(0.20, "--max-abs-weight"),
    max_gross_leverage: float = typer.Option(1.0, "--max-gross-leverage"),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Run a paper trading loop with the factor strategy weights."""
    lake, _, builder = _runtime(config)
    panels = load_universe_panels(
        builder=builder,
        exchange=exchange,
        symbols=_parse_symbols(symbols),
        market_type=MarketType(market_type),
        factor_name=factor_name,
        benchmark_symbol=benchmark_symbol,
    )
    strategy = CrossSectionalBacktester(
        assumptions=ExecutionAssumptions(
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            max_abs_weight=max_abs_weight,
            max_gross_leverage=max_gross_leverage,
        )
    )
    target_weights = strategy.build_weights(panels.factor)
    session = PaperTradingSession(
        broker=PaperBroker(starting_cash=starting_cash, fee_bps=fee_bps, slippage_bps=slippage_bps),
        risk_manager=RiskManager(
            RiskLimits(
                max_abs_weight=max_abs_weight,
                max_gross_leverage=max_gross_leverage,
            )
        ),
    )
    result = session.run(
        target_weights=target_weights,
        price_frame=panels.price,
        dollar_volume=panels.dollar_volume,
        funding_rate=panels.funding_rate,
    )
    report = render_paper_trading_report(factor_name, result)
    report_path = lake.reports_dir / "paper" / f"{factor_name}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    typer.echo(str(report_path))
    typer.echo(f"final_equity: {result.equity_curve.iloc[-1]:.6f}")
    typer.echo(f"fills: {len(result.fills)}")


@app.command()
def run_strategy(
    workflow_config: Path = typer.Option(..., "--workflow-config", help="Path to a strategy workflow YAML."),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Run the full configured workflow and persist artifacts."""
    lake, _, builder = _runtime(config)
    workflow = load_strategy_workflow(workflow_config)
    artifacts = StrategyRunner(layout=lake, builder=builder).run(workflow)
    typer.echo(f"run_id: {artifacts.run_id}")
    if artifacts.factor_report_path:
        typer.echo(f"factor_report: {artifacts.factor_report_path}")
    if artifacts.backtest_report_path:
        typer.echo(f"backtest_report: {artifacts.backtest_report_path}")
    if artifacts.paper_report_path:
        typer.echo(f"paper_report: {artifacts.paper_report_path}")
    if artifacts.manifest_path:
        typer.echo(f"manifest: {artifacts.manifest_path}")


@app.command()
def feature_manifests(
    factor_name: str | None = typer.Option(None, "--factor", help="Optional factor filter."),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """List stored feature manifests."""
    lake, _, builder = _runtime(config)
    manifests = builder.store.load_manifests(factor_name)
    typer.echo(f"manifests: {len(manifests)}")
    for item in manifests:
        typer.echo(
            f"{item['factor_name']}\t{item['symbol']}\t{item['factor_version']}\t{item['feature_path']}"
        )


@app.command()
def run_registry(
    kind: str | None = typer.Option(None, "--kind", help="Optional registry kind filter."),
    limit: int = typer.Option(20, "--limit", min=1, help="How many recent entries to show."),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """List recent workflow, experiment, and comparison runs."""
    lake, _, _ = _runtime(config)
    records = RunRegistry(lake.reports_dir).load(kind=kind)
    if not records:
        typer.echo("registry: 0")
        return

    recent = records[-limit:]
    typer.echo(f"registry: {len(records)}")
    for item in reversed(recent):
        typer.echo(
            f"{item['kind']}\t{item['name']}\t{item['run_id']}\t{item['manifest_path']}"
        )


@app.command()
def refresh_state(config: Path | None = typer.Option(None, "--config", "-c")) -> None:
    """Print incremental refresh checkpoints."""
    lake, _, _ = _runtime(config)
    checkpoints = IncrementalStateStore(lake.root_dir).list_checkpoints()
    typer.echo(f"checkpoints: {len(checkpoints)}")
    for item in checkpoints:
        typer.echo(
            f"{item.dataset}\t{item.exchange}\t{item.symbol}\t{item.market_type}\t{item.last_ts}\trows={item.rows}"
        )


@app.command()
def seed_trend_mvp(
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional app config path."),
) -> None:
    """Seed deterministic MVP perp data for baseline reports."""
    lake, _, _ = _runtime(config)
    written = seed_trend_mvp_data(lake)
    typer.echo(f"seeded {len(written)} symbols")
    for symbol, datasets in sorted(written.items()):
        typer.echo(symbol)
        for dataset, path in sorted(datasets.items()):
            typer.echo(f"  {dataset}: {path}")


@app.command()
def seed_crowding_mvp(
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional app config path."),
) -> None:
    """Seed deterministic crowding reversal MVP data for baseline reports."""
    lake, _, _ = _runtime(config)
    written = seed_crowding_mvp_data(lake)
    typer.echo(f"seeded {len(written)} symbols")
    for symbol, datasets in sorted(written.items()):
        typer.echo(symbol)
        for dataset, path in sorted(datasets.items()):
            typer.echo(f"  {dataset}: {path}")


@app.command()
def seed_shared_comparison_mvp(
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional app config path."),
) -> None:
    """Seed deterministic shared comparison baseline data."""
    lake, _, _ = _runtime(config)
    written = seed_shared_comparison_mvp_data(lake)
    typer.echo(f"seeded {len(written)} symbols")
    for symbol, datasets in sorted(written.items()):
        typer.echo(symbol)
        for dataset, path in sorted(datasets.items()):
            typer.echo(f"  {dataset}: {path}")


@app.command()
def compare_strategies(
    comparison_config: Path = typer.Option(..., "--comparison-config", help="Path to strategy comparison YAML."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional app config path."),
) -> None:
    """Run a side-by-side strategy comparison report."""
    _run_batch_command(BatchRunMode.COMPARISON, comparison_config, config)


@app.command()
def run_experiment(
    experiment_config: Path = typer.Option(..., "--experiment-config", help="Path to experiment YAML."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional app config path."),
) -> None:
    """Run a batch of workflows and persist an experiment summary."""
    _run_batch_command(BatchRunMode.EXPERIMENT, experiment_config, config)


@app.command()
def run_batch(
    mode: BatchRunMode = typer.Option(..., "--mode", help="Batch run mode: experiment or comparison."),
    batch_config: Path = typer.Option(..., "--batch-config", help="Path to batch YAML."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional app config path."),
) -> None:
    """Run a workflow batch through a unified batch entrypoint."""
    _run_batch_command(mode, batch_config, config)


@app.command()
def plan() -> None:
    """Print roadmap document location."""
    typer.echo("docs/platform-roadmap.md")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
