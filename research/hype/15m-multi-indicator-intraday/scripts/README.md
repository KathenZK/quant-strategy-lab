# Scripts

One-off research scripts for `HYPE-15M-Multi-Indicator-Intraday`.

Scripts here should:

- Prefer Binance HYPEUSDT `15m` data from `data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/`; use `data/cache` only as an explicit historical reproduction input.
- Use live-realistic next-bar entries.
- Model fees and slippage explicitly.
- Write retained JSON/CSV outputs into `../artifacts/`.

## Current Scripts

- `research_hype_15m_mii_search.py`: broad multi-indicator search that produced the first negative diagnostic.
- `research_hype_15m_mii_full_ablation.py`: locks the best combined search candidate, runs expanded time-slice backtests and one-at-a-time parameter ablation, and writes the durable `2026-06-26` ablation report.
- `research_hype_15m_mii_surface_combo_optimization.py`: combines the surface-improvement ablation parameters into an optimization grid and tests whether any combination can raise return without worsening drawdown.
