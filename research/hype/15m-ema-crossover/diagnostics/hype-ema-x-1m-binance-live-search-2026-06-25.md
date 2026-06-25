# HYPE-EMA-X 1m Binance Live-Executable EMA Search

Date: 2026-06-25

Family id: `HYPE-EMA-X`

Status: diagnostic / paper-live candidate only. Do not promote directly to live.

## Goal

The research request was to pull the latest three months of Binance HYPE futures `1m` candles, search two EMA lines for long-on-golden-cross and short-on-death-cross variants, test both fixed take-profit and trailing take-profit exits, and see whether a live-executable strategy can reach:

- Annualized factor: `>= 20x`
- Win rate: `>= 50%`
- Max drawdown: `< 20%`

Annualized factor is measured as `final_equity ** (365.25 / window_days)`, not as a guarantee of future one-year return.

## Data

- Symbol: Binance USD-M `HYPEUSDT`
- Timeframe: `1m`
- Window: `2026-03-25 00:00:00 UTC` to `2026-06-25 08:46:00 UTC`
- Rows: `133,007`
- Source: Binance public daily archive for `2026-03-25` through `2026-06-24`; Binance futures REST fallback for partial `2026-06-25`.
- Missing full days: none.
- Local cache: `data/cache/hype_ema_x_1m_live_search/HYPEUSDT_1m_2026-03-25_2026-06-25.parquet`

Cost assumption:

- Commission: `0.05%` per side.
- Slippage: `0.025%` per side.
- Round-trip cost charged in backtest: `0.15%`.

Funding, liquidation constraints, order-book depth, API outage behavior, and account-specific fee tier are not modeled.

## Search Scope

Script:

`research/hype/15m-ema-crossover/scripts/research_hype_ema_x_1m_live_search.py`

Report artifacts:

- `artifacts/hype_ema_x_1m_live_search/hype_ema_x_1m_live_search.json`
- `artifacts/hype_ema_x_1m_live_search/hype_ema_x_1m_live_search_ranking.csv`
- `artifacts/hype_ema_x_1m_live_search/hype_ema_x_1m_live_search_top_trades.csv`

Search counts:

| Item | Count |
| --- | ---: |
| EMA pairs tested | `69` |
| Coarse exit specs | `42` |
| Full exit specs | `470` |
| Filter specs | `2,872` |
| Stage-1 candidates | `43,470` |
| Stage-2 seed candidates | `77,550` |
| Final candidates evaluated | `11,488,000` |
| Final candidates with trades | `10,577,870` |
| Candidates meeting target | `1,940` |

Live-executable assumptions:

- Signals are computed only after a closed `1m` bar.
- Entry is at the next `1m` open after the cross signal.
- Long uses golden cross; short uses death cross.
- Hard stop, fixed take-profit, and trailing stop are market-stop style exits.
- If stop and take-profit are both reachable in the same `1m` candle, stop wins.
- A newly activated trailing stop cannot exit on the same candle that activates it; it is available from later candles only.
- Opposite EMA cross and max-hold exits are executed at the next `1m` open.
- Intratrade drawdown uses adverse high/low path, not only closed-trade equity.

## Best Trailing Candidate

Candidate id:

`HYPE_EMA_X_1M_FAST144_SLOW1597_trail_act140p0_trail180p0_sl140p0_hold1440_adx18_ret60-30p0_atrmin3p5_atrmax100p0_cool30`

Rule summary:

- Fast EMA: `144`
- Slow EMA: `1597`
- Entry: long on EMA144 crossing above EMA1597; short on EMA144 crossing below EMA1597.
- Entry filters:
  - `ADX14 >= 18`
  - Directional `ret60 >= -0.30%`
  - `ATR60 / close` between `0.035%` and `1.00%`
  - Cooldown: `30` bars after exit
- Exit:
  - Hard stop: `1.4%`
  - Trailing activation: `1.4%` favorable move
  - Trailing distance: `1.8%`
  - Max hold: `1,440` bars
  - Opposite cross exits at next open

Ranking winner used `3x` notional exposure:

| Metric | Value |
| --- | ---: |
| Final equity | `3.2243x` |
| Total return | `+222.43%` |
| Annualized factor | `102.46x` |
| Max drawdown | `-17.35%` |
| Win rate | `50.62%` |
| Trades | `81` |
| Profit factor | `2.14` |
| Worst trade | `-4.65%` |
| Stop-loss exits | `15` |
| Trailing-stop exits | `48` |
| Opposite-cross exits | `15` |
| Max-hold exits | `3` |

The same signal path at lower exposure:

| Exposure | Final equity | Annualized factor | Max DD | Win rate | Worst trade |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `1.0x` | `1.5287x` | `5.36x` | `-6.04%` | `50.62%` | `-1.55%` |
| `1.5x` | `1.8650x` | `11.76x` | `-8.95%` | `50.62%` | `-2.33%` |
| `2.0x` | `2.2563x` | `24.97x` | `-11.78%` | `50.62%` | `-3.10%` |
| `2.5x` | `2.7078x` | `51.37x` | `-14.59%` | `50.62%` | `-3.88%` |
| `3.0x` | `3.2243x` | `102.46x` | `-17.35%` | `50.62%` | `-4.65%` |

Interpretation:

- `2x` already clears the requested `20x` annualized factor with much lower drawdown than `3x`.
- `3x` is the ranking winner but sits closer to the drawdown ceiling and should not be the first live-trial sizing.
- Trade quality comes from trailing winners: trailing exits had `48` trades, `79.17%` win rate, and `+200.12%` summed 3x trade PnL. Stop and opposite-cross exits are pure loss buckets in this slice.

Split check for the trailing candidate:

| Slice | Exposure | Trades | Equity | Annualized factor | Max DD | Win rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| First half | `2x` | `42` | `1.474x` | `28.34x` | `-11.78%` | `47.62%` |
| Second half | `2x` | `39` | `1.531x` | `36.74x` | `-9.86%` | `53.85%` |
| First half | `3x` | `42` | `1.751x` | `125.28x` | `-17.35%` | `47.62%` |
| Second half | `3x` | `39` | `1.841x` | `175.17x` | `-14.51%` | `53.85%` |

The split is encouraging but not enough for live approval, because the same three-month window was used for selection.

## Best Fixed Take-Profit Candidate

Candidate id:

`HYPE_EMA_X_1M_FAST233_SLOW1597_fixed_tp700p0_sl280p0_hold1440_adx18_rvol1_ret60-30p0`

Rule summary:

- Fast EMA: `233`
- Slow EMA: `1597`
- Entry: same cross direction rule.
- Entry filters:
  - `ADX14 >= 18`
  - `RVOL60 >= 1.0`
  - Directional `ret60 >= -0.30%`
- Exit:
  - Fixed take-profit: `7.0%`
  - Hard stop: `2.8%`
  - Max hold: `1,440` bars
  - Opposite cross exits at next open

Exposure sensitivity:

| Exposure | Final equity | Annualized factor | Max DD | Win rate | Trades | Worst trade |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `1.0x` | `1.4775x` | `4.68x` | `-6.33%` | `51.85%` | `27` | `-2.95%` |
| `1.5x` | `1.7689x` | `9.54x` | `-9.40%` | `51.85%` | `27` | `-4.43%` |
| `2.0x` | `2.0978x` | `18.72x` | `-12.40%` | `51.85%` | `27` | `-5.90%` |
| `2.5x` | `2.4652x` | `35.44x` | `-15.34%` | `51.85%` | `27` | `-7.38%` |
| `3.0x` | `2.8717x` | `64.81x` | `-18.21%` | `51.85%` | `27` | `-8.85%` |

Interpretation:

- The fixed take-profit line can meet the target only at `>= 2.5x` exposure in this slice.
- It has only `27` trades, so it is more sample-fragile than the trailing candidate.
- Fixed TP is therefore a secondary reference, not the preferred live-trial candidate.

## Live Feasibility Decision

Do not promote this directly to live production.

A live-executable state machine can reproduce the rules, but the evidence is still an in-sample three-month search on one symbol and one venue. The proper status is:

`HYPE-EMA-X-1M-TRAIL-144-1597`: paper-live candidate, preferred trial sizing `2x`, hard cap `3x`.

Required before any real-order promotion:

- Add funding-rate accounting.
- Re-run on a later forward window without changing parameters.
- Re-run after `2026-06-25` closes so the final day is not partial.
- Audit real Binance account fee tier and live slippage from fills.
- Implement a runner that rebuilds EMA144/EMA1597, ADX14, ret60, ATR60, cooldown, trailing state, and open position state after restart.
- Use reduce-only protective stops and verify duplicate-order/idempotency behavior.
- Add emergency flat/kill switch and missing-data behavior.
- Start with paper-live or tiny live at `2x`; do not begin at the `3x` search winner.

## Implementation Notes For A Runner

State fields:

- `last_closed_bar_ts`
- `ema144`
- `ema1597`
- `adx14`
- `ret60`
- `atr60_pct`
- `position_side`
- `entry_price`
- `entry_ts`
- `best_price_since_entry`
- `trailing_active`
- `trailing_stop_price`
- `hard_stop_price`
- `cooldown_until_ts`
- `last_signal_id`
- `open_order_ids`

Execution loop:

1. Fetch closed `1m` candles only.
2. Update indicators on the newly closed candle.
3. If flat and not in cooldown, detect EMA cross from prior closed candle to current closed candle.
4. If filters pass, submit market entry for the next loop/open-equivalent execution boundary.
5. Immediately place or maintain hard stop.
6. While in position, update trailing only from closed bars; do not let an activation candle immediately stop itself out.
7. Exit on hard stop, trailing stop, opposite cross at next open, or max hold.
8. Use reduce-only exits and persist every state transition before sending the next order.

## Conclusion

The search did find candidates that satisfy the requested backtest constraints after realistic next-bar entry, conservative same-candle stop priority, and explicit cost assumptions.

The strongest practical candidate is the trailing EMA144/EMA1597 version. Use `2x` as the paper-live baseline because it still clears the requested annualized target with substantially lower drawdown than `3x`. The `3x` row is useful as an upper-bound research result, not as the default live setting.
