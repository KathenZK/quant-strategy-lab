from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import typer

from strategy_lab.data import (
    CCXTDataClient,
    DataAuthenticityAuditor,
    DataIngestionService,
    DataLakeLayout,
    DuckDBWarehouse,
    MarketType,
)
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
from strategy_lab.research import CrossQualityConfig, build_cross_quality_dataset
from strategy_lab.settings import load_settings

app = typer.Typer(
    add_completion=False,
    help="Data-first Quant Strategy Lab CLI. Strategy platform commands are archived.",
)


def _parse_since(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _parse_symbols(value: str) -> list[str]:
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def _runtime(config: Path | None) -> tuple[DataLakeLayout, DuckDBWarehouse, FeatureBuilder]:
    settings = load_settings(config)
    lake = DataLakeLayout.from_settings(settings)
    lake.ensure_directories()
    warehouse = DuckDBWarehouse(lake)
    builder = FeatureBuilder(
        warehouse=warehouse,
        store=FeatureStore(lake),
        registry=default_registry(),
    )
    return lake, warehouse, builder


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
    """Print a Binance spot USDT universe suitable for research."""
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
    """Sync Binance spot OHLCV into the standard data lake."""
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
    feed_type: int | None = typer.Option(0, "--feed-type", help="Binance Square feed type."),
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
    max_pages: int = typer.Option(100, "--max-pages", min=1, help="Stop after this many feed pages."),
    page_size: int = typer.Option(20, "--page-size", min=1, max=50, help="Posts requested per page."),
    sleep_seconds: float = typer.Option(1.0, "--sleep-seconds", min=0.0, help="Delay between page requests."),
    feed_type: int | None = typer.Option(0, "--feed-type", help="Binance Square feed type."),
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


@app.command()
def refresh_symbol(
    exchange: str = typer.Option(..., "--exchange", help="Exchange id, for example: binance"),
    symbol: str = typer.Option(..., "--symbol", help="Trading symbol, for example: BTC/USDT"),
    timeframe: str = typer.Option("1h", "--timeframe", help="Bar timeframe."),
    market_type: str = typer.Option("spot", "--market-type", help="spot or perp"),
    limit: int = typer.Option(500, "--limit", min=1, help="How many bars to fetch."),
    since: str | None = typer.Option(None, "--since", help="ISO-8601 datetime in UTC."),
    include_derivatives: bool = typer.Option(True, "--include-derivatives/--ohlcv-only", help="Fetch perp funding/open interest/basis/liquidations."),
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
            ("historical_liquidations", lambda: service.refresh_historical_liquidations(exchange=exchange, symbol=symbol, timeframe="4h", since=since_dt, limit=1000)),
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
    max_events: int | None = typer.Option(None, "--max-events", min=1, help="Optional maximum websocket messages."),
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


@app.command("build-ema-cross-quality-dataset")
def build_ema_cross_quality_dataset(
    exchange: str = typer.Option(..., "--exchange"),
    market_type: str = typer.Option("perp", "--market-type"),
    timeframe: str = typer.Option("15m", "--timeframe"),
    symbols: str | None = typer.Option(None, "--symbols", help="Comma-separated symbols. Omit to scan all local symbols."),
    benchmark_symbol: str | None = typer.Option("BTC/USDT:USDT", "--benchmark-symbol"),
    horizon_bars: int = typer.Option(384, "--horizon-bars"),
    target_atr: float = typer.Option(6.0, "--target-atr"),
    stop_atr: float = typer.Option(3.5, "--stop-atr"),
    min_bars: int = typer.Option(800, "--min-bars"),
    max_symbols: int | None = typer.Option(None, "--max-symbols"),
    output: Path = typer.Option(Path("reports/ema_cross_quality_dataset.parquet"), "--output", "-o"),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Build a multi-symbol EMA96/EMA384 cross quality event dataset."""
    lake, _, _ = _runtime(config)
    symbol_tuple = tuple(_parse_symbols(symbols)) if symbols else None
    dataset = build_cross_quality_dataset(
        lake.normalized_dir / "ohlcv",
        CrossQualityConfig(
            exchange=exchange,
            market_type=market_type,
            timeframe=timeframe,
            symbols=symbol_tuple,
            benchmark_symbol=benchmark_symbol,
            horizon_bars=horizon_bars,
            target_atr=target_atr,
            stop_atr=stop_atr,
            min_bars=min_bars,
            max_symbols=max_symbols,
        ),
    )
    if dataset.empty:
        raise typer.BadParameter("no EMA cross events were found for the requested universe")

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".csv":
        dataset.to_csv(output, index=False)
    else:
        dataset.to_parquet(output, index=False)

    typer.echo(f"events: {len(dataset)}")
    typer.echo(f"symbols: {dataset['symbol'].nunique()}")
    typer.echo(f"target_before_stop_rate: {dataset['target_before_stop'].mean():.6f}")
    typer.echo(f"output: {output}")


@app.command()
def feature_manifests(
    factor_name: str | None = typer.Option(None, "--factor", help="Optional factor filter."),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """List stored feature manifests."""
    _, _, builder = _runtime(config)
    manifests = builder.store.load_manifests(factor_name)
    typer.echo(f"manifests: {len(manifests)}")
    for item in manifests:
        typer.echo(
            f"{item['factor_name']}\t{item['symbol']}\t{item['factor_version']}\t{item['feature_path']}"
        )


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
    """Sync Binance listings and market caps, then print Binance small-cap symbols."""
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
def plan() -> None:
    """Print the project entrypoint."""
    typer.echo("README.md")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
