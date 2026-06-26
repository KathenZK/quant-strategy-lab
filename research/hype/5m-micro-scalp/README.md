# HYPE-5M-Micro-Scalp

Family id: `HYPE-5M-Micro-Scalp`

Historical alias: `HYPE-5M-MS`

This family covers Binance HYPEUSDT perpetual `5m` micro-scalp research. The target shape is high-frequency, high-win-rate, small-per-trade edge with live-executable fixed bracket exits.

It is independent from:

- `HYPE-5M-Pullback-Trail`: pullback/resume entries with ATR trailing-stop exits.
- `HYPE-1M-EMA-Crossover`: Binance HYPEUSDT `1m` EMA crossover research.
- `HYPE-15M-Multi-Indicator-Intraday`: Binance HYPEUSDT `15m` broad indicator search.
- `HYPE-EMA-Crossover` and `HYPE-EMA-Trend-Breakout`: legacy `15m` EMA families.

## Current Scope

- Data: Binance HYPEUSDT perpetual `5m` normalized OHLCV under the repository data lake.
- Execution model: closed-bar signal, next-bar open entry, immediate fixed TP/SL bracket, conservative stop-first ordering when one candle can hit both target and stop.
- Cost model: observed Binance live cost from `HYPE-5M-Pullback-Trail` audits, recorded explicitly in each search report.
- Frequency goal: roughly `3-5` completed trades per day.
- Status: first executable broad search is no-go; do not promote to live, paper-live, or dry-run candidate without a new audit that overcomes the 2026-06-26 findings.

## Canonical Entrypoints

- `decision-log.md`: family decision history.
- `diagnostics/hype-5m-micro-scalp-search-2026-06-26.md`: first executable broad search report.

## Current Finding

The 2026-06-26 search found many high-win and frequency-matched rows, but none with positive expectancy under the executable order model and observed Binance cost model. The best `3-5` trades/day row annualized only `0.23x`, and `0` configs passed the hard or audit gate.

## Directory Rules

- `scripts/`: one-off reproducible search and audit scripts for this family.
- `artifacts/`: retained JSON/CSV evidence cited by Markdown reports.
- `diagnostics/`: search reports, live-feasibility audits, and no-go records.
- `research-notes/`: exploratory notes that are not candidate specs.
- `live-specs/`: only use after a candidate has paper-audit evidence.

Do not cite a bare version number for this family. Use names such as `HYPE-5M-Micro-Scalp-search-2026-06-26` or a later explicit candidate id.
