# Quant Strategy Lab

This repository is now a data-first quantitative research archive.

The durable assets are:

- the local data lake under `data/`
- research documents under `docs/research/`
- Cursor canvas indexes under `docs/research/hype/cursor/`
- narrow data/research tooling under `src/strategy_lab/`

The old strategy platform, workflow engine, dashboard, and broad backtest layer have been retired into `archive/`.

## Read First

- `AGENTS.md`: rules for AI agents working in this repository.
- `docs/research/STRATEGY_INDEX.md`: strategy-family ids and collision rules.
- `docs/research/hype/AI_CONTEXT.md`: required HYPE reading order.
- `docs/research/hype/README.md`: HYPE research entrypoint.
- `docs/platform/strategy-lab-data-lake-conventions.md`: data lake conventions.

## Active Structure

```text
src/strategy_lab/
  data/       # data ingestion, normalization, quality, factors, features
  research/   # narrow reusable research dataset exporters
  cli.py      # data-first CLI

docs/research/
  STRATEGY_INDEX.md
  hype/
    AI_CONTEXT.md
    families/
    cursor/

scripts/data/
  fetch_polygon_equity_aggregates.py

archive/
  code/platform/
  scripts/research/
  reports/legacy/
```

## HYPE Family Rule

Do not cite bare version numbers.

Use family ids:

- `HYPE-CC-V35`: candle-count reversal family.
- `HYPE-EMA-X-V14`: EMA golden/death cross family.
- `HYPE-EMA-TB-V35`: EMA trend-breakout family.
- `MU-HYPE-XFER`: MU transfer research from HYPE trend kernels.

These are different strategies even when their version numbers match.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Check the data CLI:

```bash
./.venv/bin/quant-strategy-lab --help
./.venv/bin/quant-strategy-lab layout
./.venv/bin/quant-strategy-lab factors
```
