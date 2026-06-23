# HYPE-5M-PBTR 5m Pullback-Trail

Family id: `HYPE-5M-PBTR`

This family covers Binance HYPE USDT perpetual `5m` strategy research centered on pullback/resume entries and ATR trailing-stop exits.

It is independent from:

- `HYPE-EMA-TB`: the older 15m EMA96/384 trend-breakout / cross-exchange execution family.
- `HYPE-EMA-X`: the EMA golden/death cross and cross-quality family.
- `HYPE-CC`: the candle-count reversal family.

## Canonical Entrypoints

- `hype-5m-pullback-trail-core-ledger.md`: main ledger for `HYPE-5M-PBTR-V1/V2`.
- `hype-5m-pullback-trail-v2-combo-test-2026-06-23.md`: synchronous parameter test that promoted V2.
- `hype-5m-r05732-strategy-ablation-2026-06-23.md`: V1/R05732 full parameter explanation and ablation.

## Supporting Research

- `hype-5m-indicator-ensemble-search.md`: original 5m indicator/ensemble search.
- `hype-5m-ensemble-forward-oos-2026-06-23.md`: forward OOS check for the initial ensemble batch.
- `hype-5m-positive-payoff-search-2026-06-23.md`: positive-payoff search after rejecting high-win small-profit paths.
- `hype-5m-survival-frontier-2026-06-23.md`: survival frontier that selected R05732 for deeper research.
- `ensemble-specs/`: historical live-code handoff specs for the initial one-position ensemble batch.

## Version Scope

`HYPE-5M-PBTR-V1/V2` are local to this family. Never merge or compare them by bare version number with `HYPE-EMA-TB-V35`, `HYPE-EMA-X-V17`, or `HYPE-CC-V35`.
