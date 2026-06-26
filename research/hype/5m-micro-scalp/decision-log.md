# HYPE-5M-Micro-Scalp Decision Log

Family id: `HYPE-5M-Micro-Scalp`

Historical alias: `HYPE-5M-MS`

## Current Boundary

- This is a separate Binance HYPEUSDT perpetual `5m` family for high-frequency micro-scalp research.
- It is not a version of `HYPE-5M-Pullback-Trail`, even when it reuses EMA, RSI, MACD, Bollinger, Donchian, ATR, ADX, or volume features.
- Research conclusions must be stored under this directory, with durable JSON/CSV evidence in `artifacts/`.
- No strategy from this family may be called live-ready until order timing, bracket maintenance, restart behavior, cost sensitivity, and paper/live-dry-run reconciliation are audited.

## Research Batches

- `diagnostics/hype-5m-micro-scalp-search-2026-06-26.md`: first executable broad search for the user goal of `3-5` trades/day, high win rate, low drawdown, and small per-trade profits on Binance HYPEUSDT `5m`. Tested `12576` curated/random EMA/RSI/MACD/Bollinger/VWAP/Donchian/ATR/ADX/volume/candle-structure configs under closed-bar signal, next-open entry, immediate TP/SL bracket, stop-first same-bar ordering, next-open timeout, and observed Binance live cost. Result: `1595` configs hit the `3-5` trades/day frequency band, but `0` hit hard pass and `0` hit audit pass. The best frequency-band annualized multiple was only `0.23x`; the highest-win frequency-band rows reached about `85%` win rate but remained deeply negative because payoff and cost overwhelmed small wins.
- `diagnostics/hype-5m-micro-scalp-relaxed-rounds-2026-06-26.md`: constraint-relaxation search requested by the user after the strict no-go. Kept the data and execution model fixed, then relaxed one constraint shape per round. `R1_relax_frequency` lowered frequency to `0.10-1.00` trades/day and found `32` round-gate candidates. `R2_relax_winrate_payoff` allowed `45%+` win rate with stronger PF/payoff and found `20` round-gate candidates. `R3_live_candidate_gate` removed the high-win/micro-profit story and kept only executable positive profitability and split robustness, finding `36` round-gate candidates. Across the `88` round-gate rows, `81` passed the initial monthly live-candidate screen.
- `diagnostics/hype-5m-micro-scalp-candidate-robustness-2026-06-26.md`: local parameter-neighborhood robustness sweep around four better sample-size candidates from the relaxed rounds. Tested `749` neighborhood configs; `407` passed robust gate and `396` passed robust + monthly gate. Best balanced candidate for paper audit is `R1_relax_frequency_R01242__tp_sl_0011`: `vwap_revert`, both sides, `188` trades, `0.48` trades/day, annualized `1.32x`, win `85.11%`, PF `1.468`, avg trade `16.67 bps`, maxDD `-8.16%`, VAL PF `5.445`, FWD PF `3.550`, recent 30d `10.46%`, `3/14` negative months.

## Current Decision

- `HYPE-5M-Micro-Scalp-search-2026-06-26`: no-go for the original strict shape of `3-5` trades/day high-win micro-profit scalping.
- `HYPE-5M-Micro-Scalp-relaxed-rounds-2026-06-26` and `HYPE-5M-Micro-Scalp-candidate-robustness-2026-06-26`: paper-audit candidate found after relaxing frequency and loosening the micro-profit framing.
- The current evidence says the original high-frequency micro-profit shape is not viable under this executable model and observed Binance cost model on the available HYPEUSDT `5m` sample.
- The current best relaxed candidate is not live-ready; it may advance only to per-trade paper audit, order-maintenance audit, restart-state audit, and live-spec drafting.
- Do not promote high-win rows from this search without explicitly noting their negative PF, negative annualized multiple, and deep drawdown.
