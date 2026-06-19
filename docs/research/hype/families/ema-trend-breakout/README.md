# HYPE-EMA-TB EMA Trend Breakout

Family id: `HYPE-EMA-TB`

This family covers HYPE 15m EMA96/EMA384 trend-breakout research with ADX, volume, 1h confirmation, live-realistic execution checks, and cross-exchange execution variants.

## Canonical Specs

Use `canonical-specs/` for reproducible strategy definitions and handoff documents.

Important documents:

- `hype-v2p-strategy-spec.md`: early trend-breakout candidate.
- `hype-trend-strategy-v30-spec.md`: trend-family baseline.
- `hype-trend-strategy-v34-spec.md`: high-return/low-drawdown checkpoint.
- `hype-trend-strategy-v35-spec.md`: timeout-relaxed variant.
- `hype-trend-strategy-v36-spec.md`: Binance signal plus Hyperliquid execution.

## Do Not Mix With

- `HYPE-CC-V35`
- Any candle-count reversal document under `../candle-count-reversal/`

When citing this family, use names like `HYPE-EMA-TB-V30`, `HYPE-EMA-TB-V35`, or `HYPE-EMA-TB-V36`.
