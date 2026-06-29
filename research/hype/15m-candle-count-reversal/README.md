# HYPE-CC Candle-Count Reversal

Family id: `HYPE-CC`

This family covers HYPE 15m candle-count reversal strategies: 10 bars, 8 same-color candles, ATR-based risk controls, and later early-exit variants.

## Canonical Specs

Use `canonical-specs/` for reproducible strategy definitions and parameter records.

Important documents:

- `hype-cc-15m-milestone-comparison.md`: migrated Markdown ledger for the HYPE-CC 15m milestone comparison.
- `legacy-canvas/`: migrated historical Canvas reports for HYPE-CC experiments, robustness checks, and diagnostics.
- `hype-v13-strategy-spec.md`: core V13 specification.
- `hype-v18-atr672-strategy-spec.md`: ATR672 robust baseline.
- `hype-v21-bidirectional-opposite-three-exit-strategy-spec.md`: bidirectional early-exit variant.
- `hype-v35-reproducible-params.md`: V35 reproducibility record.

## Diagnostics

Use `diagnostics/` for overfit analysis and caveats.

Current diagnostics:

- `diagnostics/hype-v35-overfit-diagnosis.md`: V35 parameter sensitivity and overfit-risk checkpoint.
- `diagnostics/hype-cc-v35-parameter-overfit-rediagnosis-2026-06-29.md`: V35 parameter-level overfit re-diagnosis after June OOS proxy and live underperformance evidence.
- `diagnostics/hype-cc-v35-live-underperformance-review-2026-06-29.md`: V35 Binance live underperformance review; downgrades V35 to live-underperformance / execution-risk diagnostic until live-realistic replay is complete.
- `scripts/replay_hype_cc_v35_oos_proxy_2026_06_29.py`: one-off replay script for the 2026-06 OOS OHLCV proxy check.
- `artifacts/hype_cc_v35_oos_proxy_review_2026-06-29.json`: retained output from the 2026-06 OOS proxy replay.
- `artifacts/hype_pulse_aliyun_live_audit_2026-06-29.json`: retained Aliyun HypePulse live DB / log / exchange snapshot audit for the same underperformance review.

## Do Not Mix With

- `HYPE-EMA-TB-V35`
- Any trend-breakout document under `../15m-ema-trend-breakout/`

When citing this family, use names like `HYPE-CC-V13`, `HYPE-CC-V21`, or `HYPE-CC-V35`.

## Local Report Artifacts

New retained artifacts for this family should live under `artifacts/`. Top-level `reports/` is retired; migrated Canvas notes should point to retained `artifacts/` or explicit archive paths.

Historical report filename families observed for this lineage:

- `hype_v13_*`
- `hype_v18_*`
- `hype_v21_*`
- `hype_v24_*`
- `hype_v35_*`
- `hyperliquid_hype_v13_v15_v18_*`

Family identity must be checked from the linked document or migrated Canvas note before using a report. Do not infer family identity from `v35` alone.
