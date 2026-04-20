from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer

from signal_lab.config import load_settings
from signal_lab.data import CCXTDataClient, DataLakeLayout, DatasetKind, MarketType, write_dataframe
from signal_lab.factors import default_registry

app = typer.Typer(add_completion=False, help="Signal Lab research platform CLI.")


@app.command()
def layout(config: Path | None = typer.Option(None, "--config", "-c", help="Optional YAML config path.")) -> None:
    """Print data lake directories."""
    settings = load_settings(config)
    lake = DataLakeLayout.from_settings(settings)
    for key, value in lake.summary().items():
        typer.echo(f"{key}: {value}")


@app.command()
def init_dirs(config: Path | None = typer.Option(None, "--config", "-c", help="Optional YAML config path.")) -> None:
    """Create data lake directories."""
    settings = load_settings(config)
    lake = DataLakeLayout.from_settings(settings)
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
def fetch_ohlcv(
    exchange: str = typer.Option(..., "--exchange", help="Exchange id, for example: binance"),
    symbol: str = typer.Option(..., "--symbol", help="Trading symbol, for example: BTC/USDT"),
    timeframe: str = typer.Option("1h", "--timeframe", help="Bar timeframe."),
    market_type: str = typer.Option("spot", "--market-type", help="spot or perp"),
    limit: int = typer.Option(500, "--limit", min=1, help="How many bars to fetch."),
    since: str | None = typer.Option(None, "--since", help="ISO-8601 datetime in UTC."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Optional YAML config path."),
) -> None:
    """Fetch OHLCV data and store it in the raw lake."""
    settings = load_settings(config)
    lake = DataLakeLayout.from_settings(settings)
    lake.ensure_directories()
    market = MarketType(market_type)
    client = CCXTDataClient(exchange_name=exchange, market_type=market)
    since_dt = datetime.fromisoformat(since.replace("Z", "+00:00")) if since else None
    frame = client.fetch_ohlcv(symbol=symbol, timeframe=timeframe, since=since_dt, limit=limit)
    partition_date = frame["ts"].max().date()
    path = write_dataframe(
        frame,
        layout=lake,
        layer="raw",
        kind=DatasetKind.OHLCV,
        exchange=exchange,
        market_type=market,
        symbol=symbol,
        partition_date=partition_date,
    )
    typer.echo(f"saved {len(frame)} rows to {path}")


@app.command()
def plan() -> None:
    """Print roadmap document location."""
    typer.echo("docs/platform-roadmap.md")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
