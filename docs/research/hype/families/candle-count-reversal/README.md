# HYPE-CC Candle-Count Reversal

Family id: `HYPE-CC`

This family covers HYPE 15m candle-count reversal strategies: 10 bars, 8 same-color candles, ATR-based risk controls, and later early-exit variants.

## Canonical Specs

Use `canonical-specs/` for reproducible strategy definitions and parameter records.

Important documents:

- `hype-v13-strategy-spec.md`: core V13 specification.
- `hype-v18-atr672-strategy-spec.md`: ATR672 robust baseline.
- `hype-v21-bidirectional-opposite-three-exit-strategy-spec.md`: bidirectional early-exit variant.
- `hype-v35-reproducible-params.md`: V35 reproducibility record.

## Diagnostics

Use `diagnostics/` for overfit analysis and caveats.

## Do Not Mix With

- `HYPE-EMA-TB-V35`
- Any trend-breakout document under `../ema-trend-breakout/`

When citing this family, use names like `HYPE-CC-V13`, `HYPE-CC-V21`, or `HYPE-CC-V35`.
