from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import typer

from signal_lab.config import load_settings
from signal_lab.backtest import CrossSectionalBacktester, ExecutionAssumptions
from signal_lab.data import DataIngestionService, DataLakeLayout, DuckDBWarehouse, MarketType
from signal_lab.execution import PaperBroker, PaperTradingSession
from signal_lab.factors import default_registry
from signal_lab.features import FeatureBuilder, FeatureStore
from signal_lab.portfolio import RiskLimits, RiskManager
from signal_lab.reporting import render_backtest_report, render_factor_report, render_paper_trading_report
from signal_lab.research import FactorResearchLab

app = typer.Typer(add_completion=False, help="Signal Lab research platform CLI.")


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


def _load_universe_panels(
    *,
    builder: FeatureBuilder,
    exchange: str,
    symbols: list[str],
    market_type: MarketType,
    factor_name: str,
    benchmark_symbol: str | None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    factor_series: dict[str, pd.Series] = {}
    price_series: dict[str, pd.Series] = {}
    dollar_volume_series: dict[str, pd.Series] = {}
    funding_series: dict[str, pd.Series] = {}

    for symbol in symbols:
        market = builder.load_symbol_frame(
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            benchmark_symbol=benchmark_symbol,
        )
        if market.empty:
            raise ValueError(f"no normalized market data found for {symbol} on {exchange}/{market_type.value}")

        bundle = builder.build_symbol_features(
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            benchmark_symbol=benchmark_symbol,
            factor_names=[factor_name],
        )
        if bundle.empty or factor_name not in bundle.columns:
            raise ValueError(f"factor {factor_name} could not be computed for {symbol}")

        index = pd.to_datetime(market["ts"], utc=True)
        price_series[symbol] = pd.Series(market["close"].to_numpy(), index=index)
        dollar_volume_series[symbol] = pd.Series((market["close"] * market["volume"]).to_numpy(), index=index)
        if "funding_rate" in market.columns:
            funding_series[symbol] = pd.Series(market["funding_rate"].to_numpy(), index=index)

        factor_index = pd.to_datetime(bundle["ts"], utc=True)
        factor_series[symbol] = pd.Series(bundle[factor_name].to_numpy(), index=factor_index)

    factor_panel = pd.DataFrame(factor_series).sort_index()
    price_panel = pd.DataFrame(price_series).sort_index()
    dollar_volume_panel = pd.DataFrame(dollar_volume_series).sort_index() if dollar_volume_series else None
    funding_panel = pd.DataFrame(funding_series).sort_index() if funding_series else None

    aligned_index = factor_panel.index.intersection(price_panel.index)
    if dollar_volume_panel is not None:
        aligned_index = aligned_index.intersection(dollar_volume_panel.index)
    if funding_panel is not None:
        aligned_index = aligned_index.intersection(funding_panel.index)

    factor_panel = factor_panel.loc[aligned_index]
    price_panel = price_panel.loc[aligned_index]
    if dollar_volume_panel is not None:
        dollar_volume_panel = dollar_volume_panel.loc[aligned_index]
    if funding_panel is not None:
        funding_panel = funding_panel.loc[aligned_index]
    return factor_panel, price_panel, dollar_volume_panel, funding_panel


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
        ):
            try:
                paths = action()
                typer.echo(f"{name} raw={paths['raw']}")
                typer.echo(f"{name} normalized={paths['normalized']}")
            except NotImplementedError as exc:
                typer.echo(f"{name} skipped: {exc}")


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
    saved = builder.persist_bundle(bundle)
    typer.echo(f"saved {len(saved)} factor files")
    for name, path in sorted(saved.items()):
        typer.echo(f"{name}: {path}")


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
    factor_panel, price_panel, _, _ = _load_universe_panels(
        builder=builder,
        exchange=exchange,
        symbols=_parse_symbols(symbols),
        market_type=MarketType(market_type),
        factor_name=factor_name,
        benchmark_symbol=benchmark_symbol,
    )
    diagnostics = FactorResearchLab().evaluate(factor_panel, price_panel)
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
    factor_panel, price_panel, dollar_volume, funding_panel = _load_universe_panels(
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
        factor_frame=factor_panel,
        price_frame=price_panel,
        dollar_volume=dollar_volume,
        funding_rate=funding_panel,
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
    factor_panel, price_panel, dollar_volume, funding_panel = _load_universe_panels(
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
    target_weights = strategy.build_weights(factor_panel)
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
        price_frame=price_panel,
        dollar_volume=dollar_volume,
        funding_rate=funding_panel,
    )
    report = render_paper_trading_report(factor_name, result)
    report_path = lake.reports_dir / "paper" / f"{factor_name}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    typer.echo(str(report_path))
    typer.echo(f"final_equity: {result.equity_curve.iloc[-1]:.6f}")
    typer.echo(f"fills: {len(result.fills)}")


@app.command()
def plan() -> None:
    """Print roadmap document location."""
    typer.echo("docs/platform-roadmap.md")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
