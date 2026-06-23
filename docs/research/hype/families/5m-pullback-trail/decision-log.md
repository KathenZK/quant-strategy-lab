# HYPE-5M-PBTR Decision Log

Family id: `HYPE-5M-PBTR`

This is the family-level reading path for Binance HYPE `5m` pullback/resume and ATR trailing-stop research.

## Current Boundary

- This is a distinct HYPE strategy family.
- Do not store new `HYPE-5M-PBTR` research under `families/ema-trend-breakout/`.
- Do not infer identity from bare `V1`, `V2`, `V35`, or any other version number.
- Active package code remains data/research infrastructure; strategy truth lives in this Markdown family tree and one-off research scripts.

## Research Batch Notes

- `hype-5m-indicator-ensemble-search.md`: Binance HYPE perpetual `5m` indicator-combination search over `2025-06-01` to `2026-06-01`. No single raw or refined strategy hit `20x annualized / >=80% win / >-20% DD`; a one-position ensemble of refined high-win-rate EMA/Bollinger reversion legs did hit the full-period target. Treat as a research predecessor with material overfit risk, not a promoted live version.
- `ensemble-specs/README.md`: records the original `7` `target_pass=True` HYPE Binance `5m` one-position ensemble combinations as live-code handoff specs. They share the same refined legs with different leg counts and leverage. They remain historical supporting artifacts, not the current promoted line.
- `hype-5m-ensemble-forward-oos-2026-06-23.md`: after adding `2026-06-01` to `2026-06-23 04:00 UTC` Binance HYPE `5m` data, the earlier 7 ensemble configs failed to preserve `>=80%` win rate and `<20%` drawdown. This invalidated the high-win small-profit path as a live-ready direction.
- `hype-5m-positive-payoff-search-2026-06-23.md`: after requiring `payoff_ratio > 1`, each-slice win `>=60%`, and each-slice annualized `>=20x`, base search had zero hits. Targeted refinement produced mathematical hits, but all had unacceptable drawdown. The conclusion was to add survival constraints before discussing return.
- `hype-5m-survival-frontier-2026-06-23.md`: survival frontier required each-slice `payoff_ratio > 1`, trade counts, win floors `55%/58%/60%`, and drawdown floors `-20%/-25%/-30%`. The best useful middle candidate was `HYPE_PP_R05732__dir_htf_ge_0.688442`, with full annualized `29.07x`, worst-slice annualized `9.75x`, worst-slice win `58.29%`, and payoff `2.19`.
- `hype-5m-r05732-strategy-ablation-2026-06-23.md`: promoted R05732 into `HYPE-5M-PBTR-V1` candidate form. The ablation showed `trail_atr=0.75` and `min_hold_bars=6` are core; deleting final `dir_htf` greatly increases frequency and return but lowers worst-slice win; `pullback_buffer=0.01` and removing/raising fixed take profit were the best follow-up directions.
- `hype-5m-pullback-trail-core-ledger.md`: main ledger for `HYPE-5M-PBTR-V1/V2`.
- `hype-5m-pullback-trail-v2-combo-test-2026-06-23.md`: tested `10240` synchronous combinations around V1 ablation findings; `1568` passed V2 gate. Promoted `HYPE-5M-PBTR-V2` with `pullback_buffer=0.01`, `tp_atr=99`, `stop_atr=0.5`, `roc_window=96`, `min_efficiency=0`, and `dir_htf>=0.5`.

## Current Decision

- `HYPE-5M-PBTR-V1`: keep as the cleaner win-rate baseline dry-run candidate.
- `HYPE-5M-PBTR-V2`: current main return candidate for dry-run, higher frequency and payoff but slightly lower win rate.
- Both V1 and V2 require live dry-run evidence before production sizing.
