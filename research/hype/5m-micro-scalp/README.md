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
- Original frequency goal: roughly `3-5` completed trades per day.
- Current relaxed-search boundary: profitable candidates appeared only after relaxing frequency down to roughly `0.3-0.5` trades/day. This family has paper-audit candidates, but no live-ready strategy yet.

## Canonical Entrypoints

- `decision-log.md`: family decision history.
- `diagnostics/hype-5m-micro-scalp-search-2026-06-26.md`: first executable broad search report.
- `diagnostics/hype-5m-micro-scalp-relaxed-rounds-2026-06-26.md`: round-by-round relaxed-constraint search.
- `diagnostics/hype-5m-micro-scalp-candidate-robustness-2026-06-26.md`: parameter-neighborhood robustness check for the relaxed candidates.
- `canonical-specs/hype-5m-micro-scalp-v1-baseline-spec.md`: `HYPE-5M-Micro-Scalp-V1` baseline spec and parameter explanation.
- `ablations/hype-5m-micro-scalp-v1-full-parameter-ablation-2026-06-29.md`: V1 one-at-a-time full parameter ablation.

## Current Finding

The first 2026-06-26 strict search found many high-win and frequency-matched rows, but none with positive expectancy under the executable order model and observed Binance cost model. The best `3-5` trades/day row annualized only `0.23x`, and `0` configs passed the hard or audit gate.

The follow-up relaxed search changed one constraint at a time:

- `R1_relax_frequency`: frequency relaxed from `3-5/day` to `0.10-1.00/day`, leaving `32` round-gate candidates.
- `R2_relax_winrate_payoff`: win-rate requirement relaxed to `45%+` while requiring stronger PF/payoff, leaving `20` round-gate candidates.
- `R3_live_candidate_gate`: high-win micro-profit framing removed, keeping only executable positive profitability and split robustness, leaving `36` round-gate candidates.

The subsequent robustness sweep tested `749` local neighborhood configs around the better sample-size candidates. `407` passed the robust gate and `396` also passed the monthly gate. The current best balanced paper-audit candidate is:

- `R1_relax_frequency_R01242__tp_sl_0011`: `vwap_revert`, both sides, `188` trades, `0.48` trades/day, annualized `1.32x`, win rate `85.11%`, PF `1.468`, average trade `16.67 bps`, maxDD `-8.16%`, VAL PF `5.445`, FWD PF `3.550`, recent 30d return `10.46%`, `3/14` negative months.

This candidate is now recorded as `HYPE-5M-Micro-Scalp-V1` baseline. The 2026-06-29 full parameter ablation tested `103` configs (`1` baseline + `102` one-at-a-time variants): V1 is most dependent on keeping `entry_style=vwap_revert`, `require_trend=true`, `ema_slow=96`, and `vwap_dev_bps=75`; TP/SL, hold/cooldown, ATR bounds, and distance filters have wider viable neighborhoods.

This is still a candidate for paper audit / live-spec drafting only. It still needs per-trade path review, order maintenance audit, restart-state audit, and paper/live-dry-run reconciliation before any real capital deployment.

## Directory Rules

- `scripts/`: one-off reproducible search and audit scripts for this family.
- `artifacts/`: retained JSON/CSV evidence cited by Markdown reports.
- `diagnostics/`: search reports, live-feasibility audits, and no-go records.
- `research-notes/`: exploratory notes that are not candidate specs.
- `live-specs/`: only use after a candidate has paper-audit evidence.

Do not cite a bare version number for this family. Use names such as `HYPE-5M-Micro-Scalp-search-2026-06-26` or a later explicit candidate id.
