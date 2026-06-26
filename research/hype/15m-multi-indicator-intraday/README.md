# HYPE-15M-Multi-Indicator-Intraday

Family id: `HYPE-15M-MII`

This family covers Binance HYPEUSDT perpetual `15m` multi-indicator intraday research. It is a separate exploratory family for combining trend, momentum, volatility, volume, and structure indicators into live-executable next-bar strategies.

Do not merge this with:

- `HYPE-EMA-Crossover`: earlier EMA golden/death cross lineage.
- `HYPE-EMA-Trend-Breakout`: later EMA96/EMA384 trend-breakout lineage.
- `HYPE-Candle-Count-Reversal`: candle color-count reversal lineage.

## Scope

- Data source: Binance USD-M futures HYPEUSDT `15m` candles.
- Active research target: high-frequency enough for intraday paper/live diagnostics, while preserving live-realistic next-open entries and stop/target handling.
- Indicator surface: RSI, MACD, EMA, ADX/DI, ATR, Donchian, Bollinger, volume/relative-volume, candle structure, and regime filters.

## Required Evidence

- Search scripts live under `scripts/`.
- Durable JSON/CSV artifacts live under `artifacts/`.
- Markdown conclusions, diagnostics, and promotion or rejection notes stay under this family directory.

## Current Status

- `2026-06-25`: family opened for a Binance HYPE `15m` multi-indicator intraday search targeting high annualized return, max drawdown <= 20%, win rate >= 70%, and roughly 1-2 trades/day if feasible.
- `2026-06-25`: first broad search completed. No candidate met annual return >= 2000%, max drawdown <= 20%, and win rate >= 70% simultaneously. Durable diagnostic: `diagnostics/hype-15m-mii-search-2026-06-25.md`.
- `2026-06-26`: best combined candidate received time-slice backtests and full one-at-a-time parameter ablation. Result remains negative: `0/55` variants met the full target/stability gate, baseline Last90 annualized return stayed negative at `-5.26%`, and the cache source lacks full standard data-lake fields. Durable ablation: `ablations/hype-15m-mii-full-ablation-2026-06-26.md`.
- `2026-06-26`: surface-improvement parameters were combined into an optimization grid. Result remains negative: `0/594` non-baseline combinations achieved higher annualized return with no worse drawdown plus trade-shape/recent-stability gates. Durable diagnostic: `ablations/hype-15m-mii-surface-combo-optimization-2026-06-26.md`.
