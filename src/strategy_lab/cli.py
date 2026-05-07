from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import typer
import pandas as pd

from strategy_lab.journal.batches import BatchRunMode
from strategy_lab.journal.batches.service import load_batch_for_mode, run_workflow_batch
from strategy_lab.settings import load_settings
from strategy_lab.data import CCXTDataClient, DataAuthenticityAuditor, DataIngestionService, DataLakeLayout, DuckDBWarehouse, MarketType
from strategy_lab.journal import BacktestJournal, ExperimentRunner, load_experiment_config
from strategy_lab.data.factors import default_registry
from strategy_lab.data.features import FeatureBuilder, FeatureStore
from strategy_lab.data.ingest import (
    BinanceSpotUniverseConfig,
    BinanceSquareClient,
    candidate_symbols_from_markets,
    rank_symbols_by_quote_volume,
    select_binance_spot_universe,
    sync_small_cap_universe,
    write_square_posts,
)
from strategy_lab.data.ingest.market_caps import DEFAULT_MARKET_CAP_THRESHOLD_USD
from strategy_lab.workflow import (
    ExecutionAssumptions,
    IncrementalStateStore,
    RefreshOptions,
    RiskLimits,
    StrategyRunner,
    StrategyWorkflowConfig,
    StrategyWorkflowSpec,
    UniverseOptions,
    build_strategy_scan_result,
    load_strategy_workflow,
    strategy_workflow_from_code,
)

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


def _factor_workflow(
    *,
    command_name: str,
    exchange: str,
    symbols: str,
    factor_name: str,
    market_type: str,
    benchmark_symbol: str | None,
    execution: ExecutionAssumptions | None = None,
    risk: RiskLimits | None = None,
    run_factor_report: bool,
    run_backtest: bool,
    run_paper_trade: bool,
) -> StrategyWorkflowConfig:
    market = MarketType(market_type)
    return StrategyWorkflowConfig(
        strategy=StrategyWorkflowSpec(
            name=f"{command_name}__{factor_name}",
            exchange=exchange,
            market_type=market,
            symbols=_parse_symbols(symbols),
            benchmark_symbol=benchmark_symbol,
            strategy_type="factor",
            factor_name=factor_name,
        ),
        refresh=RefreshOptions(enabled=False),
        execution=execution or ExecutionAssumptions(),
        risk=risk or RiskLimits(),
        run_factor_report=run_factor_report,
        run_backtest=run_backtest,
        run_paper_trade=run_paper_trade,
    )


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


def _with_cli_local_universe(
    workflow: StrategyWorkflowConfig,
    *,
    min_avg_dollar_volume: float,
    min_history_bars: int,
    max_symbols: int,
) -> StrategyWorkflowConfig:
    return replace(
        workflow,
        universe=UniverseOptions(
            source="local_binance_spot",
            min_avg_dollar_volume=min_avg_dollar_volume,
            min_history_bars=min_history_bars,
            max_symbols=max_symbols,
        ),
    )


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


def _print_authenticity_summary(summary) -> None:
    typer.echo(f"dry_run: {str(summary.dry_run).lower()}")
    typer.echo(f"blocked_patterns: {','.join(summary.blocked_patterns)}")
    typer.echo(f"allowed_sources: {','.join(summary.allowed_sources)}")
    typer.echo(f"blocked_files: {summary.blocked_files}")
    typer.echo(f"blocked_rows: {summary.blocked_rows}")
    typer.echo(f"quarantined_files: {summary.quarantined_files}")


@app.command("audit-real-data")
def audit_real_data(
    report_path: Path | None = typer.Option(None, "--report-path", help="Optional JSON authenticity report path."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional YAML config path."),
) -> None:
    """Audit active data lake layers for synthetic, proxy, or interpolated sources."""
    lake, _, _ = _runtime(config)
    summary = DataAuthenticityAuditor(lake).audit(report_path=report_path)
    _print_authenticity_summary(summary)
    if report_path:
        typer.echo(f"report: {report_path}")


@app.command("clean-non-real-data")
def clean_non_real_data(
    execute: bool = typer.Option(False, "--execute", help="Quarantine non-real rows/files. Defaults to dry-run."),
    keep_features: bool = typer.Option(False, "--keep-features", help="Keep existing feature cache even without source lineage."),
    keep_duckdb: bool = typer.Option(False, "--keep-duckdb", help="Keep DuckDB cache files."),
    report_path: Path | None = typer.Option(None, "--report-path", help="Optional JSON cleanup report path."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional YAML config path."),
) -> None:
    """Quarantine synthetic, proxy, interpolated, and unverifiable active data."""
    lake, _, _ = _runtime(config)
    summary = DataAuthenticityAuditor(lake).clean(
        dry_run=not execute,
        quarantine_unverified_features=not keep_features,
        quarantine_duckdb=not keep_duckdb,
        report_path=report_path,
    )
    _print_authenticity_summary(summary)
    if report_path:
        typer.echo(f"report: {report_path}")
    if not execute and summary.blocked_rows:
        typer.echo("next_step: rerun with --execute to quarantine these rows/files")


@app.command()
def factors() -> None:
    """List built-in factors and metadata."""
    registry = default_registry()
    for metadata in registry.list_metadata():
        typer.echo(
            f"{metadata.name}\t{metadata.category}\tlookback={metadata.lookback}\tmarkets={','.join(metadata.market_types)}"
        )


@app.command()
def binance_spot_universe(
    min_avg_dollar_volume: float = typer.Option(1_000_000.0, "--min-avg-dollar-volume"),
    avg_volume_window: int = typer.Option(30, "--avg-volume-window", min=1),
    min_history_bars: int = typer.Option(180, "--min-history-bars", min=1),
    metadata_only: bool = typer.Option(False, "--metadata-only", help="Skip local OHLCV history and liquidity filters."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional YAML config path."),
) -> None:
    """Print a Binance spot USDT universe suitable for CTA workflows."""
    _, warehouse, _ = _runtime(config)
    universe_config = BinanceSpotUniverseConfig(
        min_avg_dollar_volume=min_avg_dollar_volume,
        avg_volume_window=avg_volume_window,
        min_history_bars=min_history_bars,
    )
    markets = CCXTDataClient(exchange_name="binance", market_type=MarketType.SPOT).load_markets()
    candidates = candidate_symbols_from_markets(markets, config=universe_config)
    symbols = (
        candidates
        if metadata_only
        else select_binance_spot_universe(
            warehouse,
            exchange="binance",
            config=universe_config,
            candidate_symbols=candidates,
        )
    )
    for symbol in symbols:
        typer.echo(symbol)


@app.command()
def sync_binance_spot_ohlcv(
    symbols: str | None = typer.Option(None, "--symbols", help="Comma-separated symbols. Defaults to ranked USDT spot symbols."),
    timeframe: str = typer.Option("1h", "--timeframe"),
    limit: int = typer.Option(1000, "--limit", min=1),
    since_days: int | None = typer.Option(None, "--since-days", min=1, help="Fetch bars starting this many days back."),
    max_symbols: int = typer.Option(20, "--max-symbols", help="0 means no cap."),
    min_quote_volume: float = typer.Option(5_000_000.0, "--min-quote-volume"),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional YAML config path."),
) -> None:
    """Sync Binance spot OHLCV for a local CTA research universe."""
    lake, _, _ = _runtime(config)
    service = DataIngestionService(lake)
    client = CCXTDataClient(exchange_name="binance", market_type=MarketType.SPOT)

    if symbols:
        selected = _parse_symbols(symbols)
    else:
        universe_config = BinanceSpotUniverseConfig(min_avg_dollar_volume=min_quote_volume)
        markets = client.load_markets()
        candidates = candidate_symbols_from_markets(markets, config=universe_config)
        if max_symbols <= 0 and min_quote_volume <= 0:
            selected = candidates
        else:
            tickers = client.fetch_tickers()
            selected = rank_symbols_by_quote_volume(
                candidates,
                tickers,
                min_quote_volume=min_quote_volume,
                max_symbols=None if max_symbols <= 0 else max_symbols,
            )

    since = None if since_days is None else datetime.now(timezone.utc) - timedelta(days=since_days)
    typer.echo(f"symbols: {len(selected)}")
    if since is not None:
        typer.echo(f"since: {since.isoformat()}")
    for symbol in selected:
        try:
            result = service.refresh_ohlcv(
                exchange="binance",
                symbol=symbol,
                market_type=MarketType.SPOT,
                timeframe=timeframe,
                since=since,
                limit=limit,
                drop_incomplete=True,
                client=client,
            )
        except Exception as exc:
            typer.echo(f"{symbol}: failed: {type(exc).__name__}: {exc}")
            continue
        typer.echo(f"{symbol}: rows={result['rows']} normalized={result['normalized']}")


@app.command()
def sync_binance_square_posts(
    pages: int = typer.Option(5, "--pages", min=1, help="Number of latest feed pages to fetch."),
    page_size: int = typer.Option(20, "--page-size", min=1, max=50, help="Posts requested per page."),
    sleep_seconds: float = typer.Option(1.0, "--sleep-seconds", min=0.0, help="Delay between page requests."),
    feed_type: int | None = typer.Option(0, "--feed-type", help="Binance Square feed type. 0 is the chronological public latest feed observed in testing."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional YAML config path."),
) -> None:
    """Sync publicly accessible latest Binance Square posts."""
    lake, _, _ = _runtime(config)
    client = BinanceSquareClient()
    frame = client.fetch_latest_posts(pages=pages, page_size=page_size, sleep_seconds=sleep_seconds, feed_type=feed_type)
    paths = write_square_posts(lake, frame)
    typer.echo(f"rows: {len(frame)}")
    typer.echo(f"unique_posts: {frame['post_id'].nunique() if not frame.empty else 0}")
    if not frame.empty:
        typer.echo(f"ts_range: {frame['ts'].min().isoformat()} -> {frame['ts'].max().isoformat()}")
    for path in paths:
        typer.echo(f"normalized: {path}")


@app.command()
def backfill_binance_square_posts(
    hours: float = typer.Option(1.0, "--hours", min=0.01, help="Backfill posts newer than this many hours ago."),
    max_pages: int = typer.Option(100, "--max-pages", min=1, help="Stop after this many feed pages even if the window is not exhausted."),
    page_size: int = typer.Option(20, "--page-size", min=1, max=50, help="Posts requested per page."),
    sleep_seconds: float = typer.Option(1.0, "--sleep-seconds", min=0.0, help="Delay between page requests."),
    feed_type: int | None = typer.Option(0, "--feed-type", help="Binance Square feed type. 0 is the chronological public latest feed observed in testing."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional YAML config path."),
) -> None:
    """Backfill public Binance Square posts until the requested time window is covered."""
    lake, _, _ = _runtime(config)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    client = BinanceSquareClient()
    frame = client.fetch_posts_since(
        since=pd.Timestamp(since),
        page_size=page_size,
        max_pages=max_pages,
        sleep_seconds=sleep_seconds,
        feed_type=feed_type,
    )
    paths = write_square_posts(lake, frame)
    typer.echo(f"since: {since.isoformat()}")
    typer.echo(f"rows: {len(frame)}")
    typer.echo(f"unique_posts: {frame['post_id'].nunique() if not frame.empty else 0}")
    if not frame.empty:
        typer.echo(f"ts_range: {frame['ts'].min().isoformat()} -> {frame['ts'].max().isoformat()}")
    for path in paths:
        typer.echo(f"normalized: {path}")


def _render_scan_table(title: str, rows) -> None:
    typer.echo(title)
    if not rows:
        typer.echo("  <none>")
        return
    for item in rows:
        signal = "" if item.signal is None else f"{item.signal:.4f}"
        price = "" if item.price is None else f"{item.price:.8g}"
        typer.echo(
            f"  {item.symbol}\taction={item.action}\ttarget={item.target_weight:.4f}"
            f"\tprevious={item.previous_weight:.4f}\tsignal={signal}\tprice={price}"
        )


@app.command()
def scan_spot_cta(
    workflow_config: Path = typer.Option(..., "--workflow-config", help="Path to a spot CTA workflow YAML."),
    use_local_universe: bool = typer.Option(False, "--use-local-universe", help="Use locally available OHLCV symbols instead of config symbols."),
    min_avg_dollar_volume: float = typer.Option(1_000_000.0, "--min-avg-dollar-volume"),
    min_history_bars: int = typer.Option(120, "--min-history-bars", min=1),
    max_symbols: int = typer.Option(0, "--max-symbols", help="0 means no cap."),
    top_n: int = typer.Option(20, "--top-n", min=1),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Scan latest spot CTA signals and print buy/hold/sell/watch decisions."""
    _, _, builder = _runtime(config)
    workflow = load_strategy_workflow(workflow_config)

    if use_local_universe:
        workflow = _with_cli_local_universe(
            workflow,
            min_avg_dollar_volume=min_avg_dollar_volume,
            min_history_bars=min_history_bars,
            max_symbols=max_symbols,
        )

    prepared = StrategyRunner(layout=builder.store.layout, builder=builder).workflow_service.prepare(workflow)
    if prepared.target_weights is None:
        raise typer.BadParameter("scan-spot-cta requires a strategy workflow that builds target weights")

    scan = build_strategy_scan_result(
        signal_frame=prepared.signal_frame,
        target_weights=prepared.target_weights,
        price_frame=prepared.panels.price,
        top_n=top_n,
    )
    typer.echo(f"scan_ts: {scan.ts.isoformat()}")
    typer.echo(f"symbols: {len(prepared.target_weights.columns)}")
    _render_scan_table("## Sell", scan.by_action("sell"))
    _render_scan_table("## Buy", scan.by_action("buy"))
    _render_scan_table("## Hold", scan.by_action("hold"))
    _render_scan_table("## Watchlist", scan.watchlist)


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
    workflow = _factor_workflow(
        command_name="factor-report",
        exchange=exchange,
        symbols=symbols,
        factor_name=factor_name,
        market_type=market_type,
        benchmark_symbol=benchmark_symbol,
        run_factor_report=True,
        run_backtest=False,
        run_paper_trade=False,
    )
    artifacts = StrategyRunner(layout=lake, builder=builder).run(workflow)
    if artifacts.factor_report_path:
        typer.echo(artifacts.factor_report_path)
    if artifacts.manifest_path:
        typer.echo(f"manifest: {artifacts.manifest_path}")


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
    workflow = _factor_workflow(
        command_name="backtest-factor",
        exchange=exchange,
        symbols=symbols,
        factor_name=factor_name,
        market_type=market_type,
        benchmark_symbol=benchmark_symbol,
        execution=ExecutionAssumptions(
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        ),
        risk=RiskLimits(
            max_abs_weight=max_abs_weight,
            max_gross_leverage=max_gross_leverage,
        ),
        run_factor_report=False,
        run_backtest=True,
        run_paper_trade=False,
    )
    artifacts = StrategyRunner(layout=lake, builder=builder).run(workflow)
    if artifacts.backtest_report_path:
        typer.echo(artifacts.backtest_report_path)
    if artifacts.manifest_path:
        typer.echo(f"manifest: {artifacts.manifest_path}")
    for key, value in artifacts.backtest_metrics.items():
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
    workflow = _factor_workflow(
        command_name="paper-trade",
        exchange=exchange,
        symbols=symbols,
        factor_name=factor_name,
        market_type=market_type,
        benchmark_symbol=benchmark_symbol,
        execution=ExecutionAssumptions(
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            starting_cash=starting_cash,
        ),
        risk=RiskLimits(
            max_abs_weight=max_abs_weight,
            max_gross_leverage=max_gross_leverage,
        ),
        run_factor_report=False,
        run_backtest=False,
        run_paper_trade=True,
    )
    artifacts = StrategyRunner(layout=lake, builder=builder).run(workflow)
    if artifacts.paper_report_path:
        typer.echo(artifacts.paper_report_path)
    if artifacts.manifest_path:
        typer.echo(f"manifest: {artifacts.manifest_path}")
    typer.echo(f"final_equity: {artifacts.paper_summary.get('final_equity', 0.0):.6f}")
    typer.echo(f"fills: {int(artifacts.paper_summary.get('fill_count', 0.0))}")


@app.command()
def run_strategy(
    strategy_type: str = typer.Argument(..., help="Strategy type to run, e.g. donchian_hold_72h."),
    exchange: str = typer.Option("binance", "--exchange"),
    market_type: MarketType = typer.Option(MarketType.SPOT, "--market-type"),
    timeframe: str = typer.Option("1h", "--timeframe"),
    symbols: str | None = typer.Option(None, "--symbols", help="Comma-separated symbols. Defaults come from strategy code."),
    use_local_universe: bool = typer.Option(False, "--use-local-universe", help="Use locally available Binance spot OHLCV symbols instead of config symbols."),
    min_avg_dollar_volume: float = typer.Option(1_000_000.0, "--min-avg-dollar-volume"),
    min_history_bars: int = typer.Option(120, "--min-history-bars", min=1),
    max_symbols: int = typer.Option(0, "--max-symbols", help="0 means no cap."),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Run a strategy from code defaults and persist artifacts."""
    lake, _, builder = _runtime(config)
    workflow = strategy_workflow_from_code(
        strategy_type,
        exchange=exchange,
        market_type=market_type,
        timeframe=timeframe,
        symbols=_parse_symbols(symbols) if symbols else None,
        use_local_universe=use_local_universe,
        min_avg_dollar_volume=min_avg_dollar_volume,
        min_history_bars=min_history_bars,
        max_symbols=max_symbols,
    )
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


@app.command("backtest-journal")
def backtest_journal(
    kind: str | None = typer.Option(None, "--kind", help="Optional journal kind filter."),
    limit: int = typer.Option(20, "--limit", min=1, help="How many recent entries to show."),
    search: str | None = typer.Option(None, "--search", help="Optional substring filter."),
    strategy_type: str | None = typer.Option(None, "--strategy-type", help="Optional strategy type filter."),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """List recent workflow, experiment, and comparison backtest journal entries."""
    lake, _, _ = _runtime(config)
    records = BacktestJournal(lake.reports_dir, db_path=lake.run_registry_db_path).load(
        kind=kind,
        search=search,
        strategy_type=strategy_type,
        limit=limit,
    )
    if not records:
        typer.echo("backtest_journal: 0")
        return

    typer.echo(f"backtest_journal: {len(records)}")
    for item in records:
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
            f"{item.owner}\t{item.dataset}\t{item.exchange}\t{item.symbol}\t{item.market_type}\t{item.last_ts}\trows={item.rows}"
        )


@app.command("backfill-backtest-journal-db")
def backfill_run_db(config: Path | None = typer.Option(None, "--config", "-c")) -> None:
    """Backfill the SQLite backtest journal from historical JSONL entries."""
    lake, _, _ = _runtime(config)
    summary = BacktestJournal(lake.reports_dir, db_path=lake.run_registry_db_path).backfill_from_jsonl()
    typer.echo(f"sqlite: {summary['sqlite_path']}")
    typer.echo(f"processed: {summary['processed']}")
    typer.echo(f"succeeded: {summary['succeeded']}")
    typer.echo(f"failed: {summary['failed']}")
    if summary["failed_manifests"]:
        for manifest_path in summary["failed_manifests"]:
            typer.echo(f"failed_manifest: {manifest_path}")
        raise typer.Exit(code=1)


@app.command()
def compare_strategies(
    comparison_config: Path = typer.Option(..., "--comparison-config", help="Path to strategy comparison YAML."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional environment config path."),
) -> None:
    """Run a side-by-side strategy comparison report."""
    _run_batch_command(BatchRunMode.COMPARISON, comparison_config, config)


@app.command()
def run_experiment(
    experiment_config: Path = typer.Option(..., "--experiment-config", help="Path to experiment YAML."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional environment config path."),
) -> None:
    """Run a batch of workflows and persist an experiment summary."""
    experiment = load_experiment_config(experiment_config)
    artifacts = ExperimentRunner(workspace_root=Path.cwd(), app_config_path=config).run(experiment)
    typer.echo(f"run_id: {artifacts.run_id}")
    typer.echo(f"report: {artifacts.report_path}")
    typer.echo(f"manifest: {artifacts.manifest_path}")
    if artifacts.winner:
        typer.echo(f"winner: {artifacts.winner.strategy_name}")


@app.command()
def run_batch(
    mode: BatchRunMode = typer.Option(..., "--mode", help="Batch run mode: experiment or comparison."),
    batch_config: Path = typer.Option(..., "--batch-config", help="Path to batch YAML."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional environment config path."),
) -> None:
    """Run a workflow batch through a unified batch entrypoint."""
    _run_batch_command(mode, batch_config, config)


@app.command("sync-small-cap-universe")
def sync_small_cap_universe_command(
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        envvar="DATABASE_URL",
        help="PostgreSQL connection URL. Defaults to DATABASE_URL.",
    ),
    schema: str = typer.Option("qsl", "--schema", help="Target PostgreSQL schema."),
    threshold_usd: float = typer.Option(
        DEFAULT_MARKET_CAP_THRESHOLD_USD,
        "--threshold-usd",
        min=0.01,
        help="Maximum market cap in USD.",
    ),
    quote_assets: str = typer.Option("USDT", "--quote-assets", help="Comma-separated Binance quote assets."),
    coingecko_max_pages: int = typer.Option(10, "--coingecko-max-pages", min=1, help="CoinGecko pages to fetch."),
    coingecko_per_page: int = typer.Option(250, "--coingecko-per-page", min=1, max=250, help="CoinGecko page size."),
    coingecko_page_delay_seconds: float = typer.Option(
        2.0,
        "--coingecko-page-delay-seconds",
        min=0.0,
        help="Delay between CoinGecko page requests to reduce rate-limit errors.",
    ),
    market_cap_source: str = typer.Option(
        "coinpaprika",
        "--market-cap-source",
        help="Market cap source: coinpaprika or coingecko.",
    ),
    coingecko_api_key: str | None = typer.Option(
        None,
        "--coingecko-api-key",
        envvar="COINGECKO_API_KEY",
        help="Optional CoinGecko demo API key.",
    ),
    include_inactive: bool = typer.Option(
        False,
        "--include-inactive/--active-only",
        help="Include inactive Binance spot symbols.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Fetch and filter without writing to PostgreSQL."),
    output_limit: int = typer.Option(50, "--output-limit", min=1, help="How many matched assets to print."),
) -> None:
    """Sync Binance listings and CoinGecko market caps, then print Binance small-cap symbols."""
    parsed_quote_assets = tuple(item.strip().upper() for item in quote_assets.split(",") if item.strip())
    if not parsed_quote_assets:
        raise typer.BadParameter("quote_assets cannot be empty")

    try:
        result = sync_small_cap_universe(
            database_url=database_url,
            schema=schema,
            threshold_usd=threshold_usd,
            quote_assets=parsed_quote_assets,
            include_inactive=include_inactive,
            coingecko_max_pages=coingecko_max_pages,
            coingecko_per_page=coingecko_per_page,
            coingecko_page_delay_seconds=coingecko_page_delay_seconds,
            coingecko_api_key=coingecko_api_key,
            market_cap_source=market_cap_source,
            dry_run=dry_run,
        )
    except (RuntimeError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"binance_listings: {len(result.listings)}")
    typer.echo(f"{market_cap_source}_assets: {len(result.market_caps)}")
    typer.echo(f"low_market_cap_matches: {len(result.matches)}")
    typer.echo(f"wrote_to_database: {str(result.wrote_to_database).lower()}")
    for item in result.matches[:output_limit]:
        cap = item.market_cap.market_cap_usd or 0.0
        ambiguity = " ambiguous_symbol" if item.ambiguous_symbol else ""
        typer.echo(
            f"{item.listing.symbol}\t{item.listing.base_asset}\t"
            f"{item.market_cap.asset_id}\t${cap:,.0f}{ambiguity}"
        )


@app.command()
def dashboard(
    host: str = typer.Option("127.0.0.1", "--host", help="Dashboard host."),
    port: int = typer.Option(27098, "--port", help="Dashboard port."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional environment config path."),
) -> None:
    """Serve the dashboard JSON API backend."""
    import uvicorn

    from strategy_lab.api import create_app

    uvicorn.run(create_app(config), host=host, port=port)


@app.command()
def plan() -> None:
    """Print documentation entrypoint."""
    typer.echo("README.md")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
