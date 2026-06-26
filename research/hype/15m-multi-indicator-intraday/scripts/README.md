# Scripts

One-off research scripts for `HYPE-15M-Multi-Indicator-Intraday`.

Scripts here should:

- Prefer Binance HYPEUSDT `15m` data from `data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/`; use `data/cache` only as an explicit historical reproduction input.
- Use live-realistic next-bar entries.
- Model fees and slippage explicitly.
- Write retained JSON/CSV outputs into `../artifacts/`.
