# HYPE-EMA-TB EMA Trend Breakout

Family id: `HYPE-EMA-TB`

This family covers the later HYPE 15m EMA96/EMA384 trend-breakout / chase-long-chase-short research with ADX, volume, 1h confirmation, live-realistic execution checks, and cross-exchange execution variants.

It is not the earlier `HYPE-EMA-X` golden/death cross family.

## Canonical Specs

Use `canonical-specs/` for reproducible strategy definitions and handoff documents.

Important documents:

- `hype-ema-tb-core-ledger.md`: migrated Markdown ledger for the broader HYPE-EMA-TB trend strategy research line.
- `legacy-canvas/`: migrated historical Canvas reports for HYPE-EMA-TB experiments, ablations, execution checks, and diagnostics.
- `hype-v2p-strategy-spec.md`: early trend-breakout candidate.
- `hype-trend-strategy-v30-spec.md`: trend-family baseline.
- `hype-trend-strategy-v34-spec.md`: high-return/low-drawdown checkpoint.
- `hype-trend-strategy-v35-spec.md`: timeout-relaxed variant.
- `hype-trend-strategy-v36-spec.md`: Binance signal plus Hyperliquid execution.

## Moved Out

- `HYPE-5M-PBTR`: Binance HYPE `5m` pullback + ATR trailing-stop research now lives under `../5m-pullback-trail/`.

## Do Not Mix With

- `HYPE-CC-V35`
- `HYPE-EMA-X-V14`
- `HYPE-5M-PBTR-V1` / `HYPE-5M-PBTR-V2`
- Any candle-count reversal document under `../15m-candle-count-reversal/`

When citing this family, use names like `HYPE-EMA-TB-V30`, `HYPE-EMA-TB-V35`, or `HYPE-EMA-TB-V36`.

## Local Report Artifacts

New retained artifacts for this family should live under `artifacts/`. Top-level `reports/` is retired; migrated Canvas notes should point to retained `artifacts/` or explicit archive paths.

Trend-breakout reports often use filenames such as:

- `hype_ema_*`
- `hype_v30_*`
- `hype_v34_*`
- `hype_v35_*`
- `hype_v36_*`
- `hype_v15_effective_cross_*`

Family identity must be checked from the target document or migrated Canvas note. Do not infer family identity from `v35` alone.

Binance HYPE `5m` strategy research has moved to the independent `HYPE-5M-PBTR` family under `../5m-pullback-trail/README.md`.
