# HYPE-15M-TB-MII-ENS-V2 Runner Implementation Smoke 2026-07-09

Status：

```text
runner kind implemented for replay validation / continuous dry-run runtime blocked / live blocked / not dry-run handoff / not live-ready
```

## Source

- Runner repo: `/Users/ZK/OpenCode/quant-runner`
- Runner strategy kind: `hype_tb_mii_ensemble`
- Runner strategy id: `HYPE-15M-TB-MII-ENS-V2`
- Runner-side spec: `crates/quant-runner/src/runner/strategies/hype_tb_mii_ensemble/HYPE-15M-TB-MII-ENS-V2-SPEC.md`
- Validation spec: `live-specs/hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md`

## Implemented Boundary

- Added `hype_tb_mii_ensemble` strategy module with fixed code defaults for V2, V39, and MII V1.4.
- Added combo replay path for `replay-dry-run`: V39 priority, MII V1.4 secondary, global one-position loop, replay-level `preempted_by_v39`.
- 2026-07-09 Bugbot review fixes applied: V39 warmup starts after `1600` bars, V39 preempt only closes MII after a valid V39 open candidate exists, same-bar MII re-entry is blocked after V39 exits, and V39 `indicator_exit` is not overwritten by same-bar timeout.
- 2026-07-09 second-pass alignment fixes applied:
  - MII open-type exits (timeout + gap) now settle at the current bar open before the V39 entry check, matching state-machine step 2, and allow same-bar MII re-entry after an open-type exit.
  - Replay equity is now marked per bar: V39 leg compounds close-to-close with `1 + pnl - cost` exit combination (engine `close_position` exact); MII leg marks anchored to entry equity with full round-trip `0.0028` pre-deducted and a zero floor (engine `close_mii_record` exact). Funding remains excluded on the Binance public-kline smoke path.
  - `h1_adx21/pdi/mdi` projection features and ratio-style `ema_spread` were promoted to the shared `indicators/` layer (`htf_adx_di`, `ema_spread`) and are now reused by both `hype_ema_x` and `hype_tb_mii_ensemble`, with shared-layer tests.
  - Default `warmup_bars` for the kind raised to `2500` per validation spec preload requirement.
  - Removed the duplicated full validation-spec copy from the runner strategy directory; the runner-side SPEC now declares loop-order/mark alignment and the remaining known differences (funding excluded; gap-through-stop booked at bar open via shared `trading/bracket.rs` with runner exit-reason names mapped 1:1 to research labels).
- Added disabled validation TOML instance: `configs/dryrun.toml` / `hype-tb-mii-ens-v2-validation`.
- Continuous dry-run/live runtime is intentionally blocked. The current runner cannot yet execute V39 K+2 pending open entries, atomic live preempt close-confirm-open, restart recovery, kill switch, notional caps, or funding reconciliation.

## Smoke Command

```bash
cargo run -- replay-dry-run --config configs/dryrun.toml --name hype-tb-mii-ens-v2-validation --limit 2500
```

Observation window from command output (2026-07-09 second pass, after alignment fixes):

```text
replay_start_ts = 2026-06-29T23:45:00+00:00
replay_end_ts   = 2026-07-09T08:30:00+00:00
bars_replayed   = 900
```

Runner config summary:

```text
symbol = HYPE/USDT:USDT
timeframe = 15m
trend = ema_tb_v39
mii = mii_v14
preempt_secondary = true
global_position_limit = 1
```

Smoke output summary:

```text
trade_count = 3
trend_trades = 3
mii_trades = 0
preempts = 0
win_rate = 0.6666666666666666
cumulative_return = 0.10203493281320153
max_drawdown = -0.14520172126190045
```

Compared with the first-pass smoke (same trades, cumulative_return 0.1044, max_drawdown -0.0750): trade path is unchanged; cumulative return moved slightly because exit cost is now combined additively per the engine formula, and max_drawdown deepened because equity is now marked per bar, so intra-trade drawdown is captured instead of only trade-close equity.

This small-window smoke only confirms the runner branch executes and emits plausible structured output. It is not the standard data lake parity gate and does not satisfy the expected full-sample target of `291` trades / V39 `107` / MII V1.4 `184` / preempt `3`.

## Checks

```bash
cargo fmt
cargo clippy --all-targets --all-features
cargo test
cargo run -- smoke-test --config configs/dryrun.toml --name hype-tb-mii-ens-v2-validation
```

Results:

```text
cargo clippy --all-targets --all-features: pass
cargo test: pass, 59 library tests + 2 integration tests (2026-07-09 second pass)
smoke-test: ok = true, issues = []
```

## Decision

Implementation removes the previous blocker “strategy kind does not exist” for replay validation only. It does not remove live-executable blockers. Status remains `NO-GO / not dry-run handoff / not live-ready`.

Next gate is full standard data lake parity against `research_hype_15m_tb_mii_ensemble_backtest.py --trend v39 --mii v14`, including逐 K state, all trades, preempt count, and equity curve tolerance.
