# HYPE-EMA-X V16/V17 Trend State Search

Date: 2026-06-20

## Goal

Push the post-V14 EMA crossover lineage toward a more accurate trend-start and trend-end detector.

Target constraints:

- Win rate: `>= 80%`
- Max drawdown: `>= -20%`
- One-year return target: `>= 50x`

## Scripts

- `research/hype/15m-ema-crossover/scripts/research_hype_v16_indicator_expansion.py`
- `research/hype/15m-ema-crossover/scripts/research_hype_v17_trend_state_search.py`

## Report Artifacts

Reports are local ignored artifacts under `artifacts/`.

- `hype_v16_indicator_expansion*.json/csv`
- `hype_v16_indicator_expansion_*_okx.csv`
- `hype_v17_trend_state_search.json`
- `hype_v17_trend_state_search_ranking.csv`
- `hype_v17_trend_state_search_constraints.csv`
- `hype_v17_trend_state_search_top_trades.csv`

## Baseline

`HYPE-EMA-X-V14` on the Binance 15m data-lake slice:

- Return: `+2191.92%`
- Max drawdown: `-24.66%`
- Trades: `33`
- Win rate: `81.82%`

## V16 Research-Batch Findings

The `research_hype_v16_indicator_expansion.py` batch tested RSI/KDJ-style late pullback, late breakout, and late reset events while keeping the V14/V13 state-machine backtester.

Key finding:

- Adding early indicator entries increased trade count but diluted the original V14 trade quality.
- The useful direction was `late-only` supplemental entry after the normal V14 entry window, not early replacement of the base EMA-cross entry.
- Binance-only late supplemental candidates improved return, but OKX did not confirm the same strength. OKX top result was roughly `+931.56%`, `-26.15%` max drawdown, `70.91%` win rate.

This V16 research batch is therefore evidence, not the promoted Cursor main-ledger `HYPE-EMA-X-V16`.

## V17 Research-Batch Findings

V17 broadened the search beyond RSI/KDJ. Indicator families included:

- EMA/Donchian distance and regime age
- ATR expansion/compression
- ADX/DI trend strength
- MACD histogram
- Aroon
- Vortex
- CCI
- Williams %R
- MFI/CMF
- OBV slope
- Bollinger/Keltner squeeze
- Choppiness
- Efficiency ratio

Full V17 search:

- Candidates tested: `2185`
- Candidates satisfying all three targets: `0`

Best hard-constraint candidate (`win_rate >= 80%`, `max_dd >= -20%`):

- Name: `V17_atr18_trend7_base_age384_d075_pnlm03_either2_stop8`
- Return: `+2303.65%`
- Max drawdown: `-17.79%`
- Win rate: `90.32%`
- Trades: `31`

Highest-return candidate:

- Name: `V17_atr18_base_age384_pnlm03_either2_stop8`
- Return: `+3202.92%`
- Max drawdown: `-28.19%`
- Win rate: `86.84%`
- Trades: `38`

Best add-signal candidates increased trade count into the 60s, but win rate fell to roughly `63%` to `68%`. These are not suitable as the main trend strategy under the current target.

## Promoted Cursor Main-Ledger Versions

- `HYPE-EMA-X-V15`: promoted high-win-rate / low-drawdown row, `V17_atr18_trend7_base_age384_d075_pnlm03_either2_stop8`.
- `HYPE-EMA-X-V16`: promoted high-return row, `V17_atr18_base_age384_pnlm03_either2_stop8`.
- `HYPE-EMA-X-V17`: promoted V15/V16 hybrid row, `HYBRID_score5_dist04_atr11` / `HYPE_EMA_X_V17`, added after comparing V15 and V16. It keeps V15 high-quality entries and admits only V16 low-score satellite entries with `trend_score` 5-6, `dir_dist_ema96 <= 0.04`, and `atr_ratio96_672 <= 1.1`.
- `HYPE-EMA-X-V17.1`: promoted V17 sizing-enhanced row, `HYPE_EMA_X_V17__hq_scale=1p1`, added after V17 ablation. It keeps V17 signals unchanged and sets `hq_scale=1.1`, `lq_scale=1.0`.

The main ledger is `../hype-ema-x-core-ledger.md`. Full rules and parameters are mirrored in `hype-ema-x-v15-v16-promoted-strategy-specs.md` and `../ablations/hype-ema-x-v17-hybrid-ablation.md`. Clean spec: `../specs/hype-ema-x-v18-baseline-spec.md`.

## Interpretation

The search found a better low-drawdown version, but not the requested `50x / <20% DD / >80% win` combination.

The strongest useful filter is not a single oscillator. It is a trend-state gate:

- ATR not overheated
- composite trend score strong enough
- late re-entry can be loosened modestly after a high-MFE prior trade
- either volume or oscillator warning can confirm exits

Manual indicator combinations appear to hit a trade-off boundary: pushing return above `30x` raises drawdown above `24%`; pushing drawdown below `20%` pulls return toward `13x` to `23x`.

## Next Research Direction

Do not keep hand-stacking more indicators as the main path.

The next serious iteration should convert this into an event-quality model:

- One row per EMA-cross or late-regime event
- Labels based on future MFE/MAE, target-before-stop, and drawdown contribution
- Time-split validation
- Exchange holdout validation
- Model outputs used as entry quality score and allocation scale

This follows the historical EMA-cross quality-dataset direction and is more likely to improve trend-start detection without overfitting a single HYPE year. The old generic active exporter has since been removed from `src/`; any renewed dataset export should live as an explicit family script under this research directory.
