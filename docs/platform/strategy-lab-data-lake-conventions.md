# Data Lake Conventions

This project is a data-first quantitative research archive.

The data lake is the primary engineering asset. Strategy code is no longer the main organizing layer.

## Core Principle

- There is one local data lake: `data/raw`, `data/normalized`, and `data/features`.
- Do not create strategy-specific data roots.
- Research scripts may be temporary, but data identity must remain stable.
- Reports under `reports/` are local artifacts and are ignored by git.
- Durable conclusions belong in `docs/research/`.

## Standard Layout

```text
data/
  raw/
  normalized/
  features/
  _state/

reports/
  _registry/
  runs/
  experiments/
```

## OHLCV Partitioning

Canonical OHLCV data is partitioned as:

```text
data/normalized/ohlcv/
  exchange=binance/
    market_type=spot/
      timeframe=1h/
        date=2026-04-30/
          symbol=btc_usdt.parquet
```

The unique business key is:

```text
exchange + market_type + timeframe + symbol + ts
```

Always filter explicitly by `exchange`, `market_type`, `timeframe`, symbol, and date range.

## Required OHLCV Fields

`normalized/ohlcv` should contain:

```text
ts
exchange
symbol
market_type
timeframe
base_asset
quote_asset
open
high
low
close
volume
quote_volume
trade_count
vwap
is_closed
source
date
```

Rules:

- `ts` uses UTC.
- `is_closed = true` bars are the safe default for research.
- `source` must identify the data source, such as `ccxt`, `binance_kline_api`, or `binance_vision`.
- Unicode symbols are legal; do not filter real exchange symbols with ASCII-only assumptions.

## Active Code Boundary

Active package code may:

- fetch data
- normalize data
- audit data authenticity
- build reusable factors/features
- export narrow research datasets

Active package code should not become a broad strategy platform again without an explicit decision.

Historical strategy, workflow, dashboard, and backtest code lives under `archive/code/platform/`.

## Research Output Rule

For a new experiment:

1. Use the standard data lake.
2. Generate a one-off script if useful.
3. Save local artifacts under `reports/`.
4. Write durable conclusions into `docs/research/`.
5. Promote code into `src/strategy_lab/` only if it is reusable data or dataset infrastructure.
