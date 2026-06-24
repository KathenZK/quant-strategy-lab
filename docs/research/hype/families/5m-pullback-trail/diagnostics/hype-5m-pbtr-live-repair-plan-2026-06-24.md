# HYPE-5M-PBTR Live Repair Plan 2026-06-24

Family id: `HYPE-5M-PBTR`

Status: repair proposal after V3.3/V4 live-realistic failure.

## Problem Statement

`HYPE-5M-PBTR-V3.3` and `HYPE-5M-PBTR-V4` are not live-ready. The failure is structural, not just a parameter bug.

The failed mechanism is:

```text
enter immediately
-> hold for N bars without strategy exits
-> compute trailing stop from lockout-period peak/trough
-> assume exit at stop level after unlock
```

In live trading, if the stop level is already crossed at unlock, the strategy cannot place a dormant stop-market order at that old price. The only executable action is market exit near the current price. That changes the trade distribution from profitable to losing.

Evidence already recorded in this family:

- `V2.1A live-realistic`: PF falls from `2.79` to `0.54`.
- `V3.3 live-realistic`: PF falls from `4.15` to `0.58`.
- `V4 live-realistic`: PF falls from `19.92` to `0.67`.
- `V3.3 reinit trailing`: reinitializing trailing at unlock removes the crossed-stop order problem, but best tested PF remains about `0.61`.

Additional quick probe in this review:

- Tested `48` executable reinit variants around V3.3/V4 using `EMA21/96`, `EMA9/96`, `EMA21/55`; `min_hold_bars` in `0/1/3/6`; and wider `trail_atr` in `1.5/2/3/4`.
- Best full-sample PF was still only about `0.69`; no tested variant reached PF `1`.
- This suggests the existing pullback entry plus reinitialized trailing exit does not have enough live-executable edge by simple exit-parameter widening.

## Decision

Do not continue promoting V3.3 or V4 as live handoff specs.

Do not judge any future candidate by the old "ignore exits during lockout, then fill at crossed stop level" backtest. That model is invalid for live execution.

The next version, if pursued, should be a new `HYPE-5M-PBTR-V5` line with an executable-first simulator.

## Non-Negotiable Execution Model

Future candidates must satisfy one of these live-valid state machines.

### Model A: Protected From Entry

```text
signal closes
-> enter next bar / live fill
-> protective stop is active immediately
-> trailing stop may update only from closed bars
-> no hidden lockout period
```

Rules:

- If a stop is active, it must be placeable as a reduce-only stop-market order.
- If price crosses the stop before order placement, exit at market, not at the old stop.
- Stop priority and gap handling must be explicitly modeled.

This is the cleanest live model. If the strategy cannot survive this model after parameter search, it should not be traded.

### Model B: Observation Then Entry

```text
signal closes
-> no position is opened
-> observe for N bars
-> enter only if confirmation still passes
-> protective stop is active immediately after entry
```

This preserves the empirical idea that the setup needs several bars to mature, but avoids carrying unprotected market risk during that period.

Possible confirmation filters:

- EMA direction is unchanged.
- price has moved at least `10-40 bps` in the intended direction from the original next-open reference.
- adverse excursion during observation is below a threshold such as `0.5-1.5 ATR`.
- close remains on the correct side of EMA fast.
- optional HTF proxy or trend-strength filter is still aligned.

### Model C: Event Quality Classifier

If Models A/B fail, stop treating the pullback signal as a direct strategy. Convert it into an event dataset:

```text
pullback_resume event
-> label future MFE/MAE and first-hit path under executable stop rules
-> train or score event quality
-> trade only high-quality events
```

This fits the earlier lesson from other HYPE research: event quality is often more durable than a raw technical rule.

## Suggested V5 Search

### Stage 1: Simulator Gate

Before searching parameters, build a single canonical executable simulator:

- observed live fee and slippage model;
- stop-market order semantics;
- crossed-stop market exit;
- gap-through-stop market exit;
- closed-bar-only trailing updates;
- no crossed stop filled at old stop price;
- one-position rule;
- explicit order-state diagnostics.

Any candidate that only works under the invalid old simulator is rejected.

### Stage 2: Immediate Protected Search

Search a lower-frequency version first:

| Parameter | Suggested grid |
| --- | --- |
| `ema_fast/ema_slow` | `21/96`, `13/96`, `9/96`, `21/72`, `21/55` |
| `pullback_buffer` | `0.005`, `0.01`, `0.02` |
| `stop_atr` | `1.0`, `1.5`, `2.0`, `3.0` |
| `trail_atr` | `1.5`, `2.0`, `3.0`, `4.0` |
| `min_hold_bars` | `0` only for protected-from-entry |
| `time_exit_bars` | `12`, `24`, `48`, `96` |
| HTF filter | disabled, `dir_htf >= 0`, `dir_htf >= 0.5` |

Reasoning:

- The old `0.25-0.5 ATR` stop is too tight for a stop active from entry.
- The old `0.5-0.75 ATR` trailing is too tight once the crossed-stop fantasy is removed.
- A real strategy should earn after wider stops and realistic costs, not only under a hidden lockout.

### Stage 3: Observation Then Entry Search

Use the original pullback signal as an observation trigger, not an entry:

| Parameter | Suggested grid |
| --- | --- |
| observation bars | `1`, `3`, `6`, `9`, `12` |
| minimum favorable move | `0`, `10`, `20`, `40 bps` |
| maximum adverse move | `50`, `100`, `150`, `200 bps`, or ATR-normalized equivalent |
| entry condition | close still on correct EMA side; EMA direction unchanged |
| stop_atr after entry | `1.0`, `1.5`, `2.0`, `3.0` |
| trail_atr after entry | `1.5`, `2.0`, `3.0`, `4.0` |
| time_exit_bars | `12`, `24`, `48`, `96` |

This is the most promising repair concept because it removes unprotected lockout risk while preserving the "wait for trend recovery to prove itself" idea.

### Stage 4: Reintroduce Quality Filters Only If Needed

If raw V5 candidates are too noisy, add filters conservatively:

- `dir_htf >= 0` or `dir_htf >= 0.5`.
- `CHOP14 <= 62` or a broader trendiness filter.
- `atr_pct` / spread filter to avoid dead volatility.
- volume or liquidity filter to avoid bad stop-market fills.

Do not add many filters at once. Every filter must pass ablation under the executable simulator.

## Acceptance Gates

The target is not "absurd annualized return". The target is a strategy that can survive live execution.

Minimum research gates:

| Metric | Gate |
| --- | ---: |
| full-sample PF | `>= 1.30` |
| worst validation-slice PF | `>= 1.05` |
| payoff | `>= 1.20` |
| average trade after costs | `> 0` and preferably `>= 3-5 bps` |
| max drawdown at 1x | better than `-25%` |
| profitable months | at least `8/14` |
| trades | enough for validation, preferably `>= 500` full sample |
| crossed-stop exits | modeled at market, never at old stop |
| order failures | candidate must define fail-safe behavior |

Dry-run gates:

- Run paper or tiny notional for `300-500` trades.
- Pass PF `>= 1.15` after real fees and slippage.
- Stop if PF `< 1` after `300` trades unless diagnostics show a temporary exchange/data problem.
- Stop if average stop slippage exceeds the research assumption by `2x`.
- Stop if actual position/order reconciliation has repeated failures.

## Practical Recommendation

For now:

1. Freeze V3.3/V4 as invalid live handoff candidates.
2. Keep any running live instance at tiny notional only, for execution telemetry, not for PnL expectation.
3. Start V5 from Model B, observation-then-entry, because the old strategy's only credible insight is that the setup may need time to mature.
4. Use Model A as the hard control. If Model B cannot outperform Model A under realistic costs, the observation layer is not adding real edge.
5. If neither Model A nor B reaches PF `1.3` with acceptable slices, abandon this 5m pullback-trailing line rather than adding more filters.

The likely successful repair, if one exists, will be lower-frequency, lower annualized-return, wider-stop, and more conservative than V3.3/V4. That is acceptable; the old high-return numbers were partly generated by a non-executable exit assumption.
