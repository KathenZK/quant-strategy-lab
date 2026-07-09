# HYPE-15M-TB-MII-ENS-V2 Runtime / Live Pilot Tracking 2026-07-09

## Status

```text
continuous dry-run runtime implemented / disabled live pilot execution chain implemented / live not enabled / not promoted
```

## Source

- Runner repo: `/Users/ZK/OpenCode/quant-runner`
- Strategy kind: `hype_tb_mii_ensemble`
- Strategy id: `HYPE-15M-TB-MII-ENS-V2`
- Runner-side spec: `crates/quant-runner/src/runner/strategies/hype_tb_mii_ensemble/HYPE-15M-TB-MII-ENS-V2-SPEC.md`
- Live validation source of truth: `live-specs/hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md`

## Implemented

- Extracted shared V2 decision helpers so replay/runtime share due-signal, candidate, MII open exit, MII bar exit, V39 intrabar exit, V39 close-state update, and MII availability rules.
- Added `TbMiiEnsembleState` as a flattened `EngineState` group for active leg, pending signal memory, V39 close-state memory, MII availability, `preempt_in_progress`, and fail-closed fields.
- Added `trading/runner/tb_mii_ensemble.rs` continuous runtime:
  - V39 pending open-exit first.
  - MII open-type exit before V39 checks.
  - V39 K+2 due entry and MII preempt.
  - V39 protection / pending exit update.
  - MII K+1 due entry only when flat and no same-execution V39 trade.
  - MII bracket/timeout maintenance.
- Implemented live order flow:
  - market entry using exchange fill average;
  - reduce-only mark-price TP and stop-market SL;
  - preempt sequence: pause -> cancel MII protections -> reduce-only market close -> confirm exchange flat -> open V39;
  - any failed preempt path records fail-closed and stops new entries.
- Implemented live recovery/fail-closed checks:
  - local flat but exchange position/open orders => fail-closed;
  - local position but exchange flat => sync close;
  - missing protection orders => one recovery attempt, then fail-closed if still missing;
  - `preempt_in_progress` blocks new entries.
- Config changes:
- `configs/dryrun.toml` adds enabled `hype-tb-mii-ens-dry-run`;
- `configs/live.toml` adds disabled `hype-tb-mii-ens-live`;
  - live validation requires dedicated account id, isolated margin, leverage `>= 3`, warmup `>= 2500`, and `live_confirm = true`.

## Validation Commands

```bash
cargo fmt --check
cargo clippy --all-targets
cargo test
cargo run -- smoke-test --config configs/dryrun.toml --name hype-tb-mii-ens-dry-run
cargo run -- replay-dry-run --config configs/dryrun.toml --name hype-tb-mii-ens-dry-run --limit 38900 --end-ts 2026-07-08T05:30:00Z
```

## Results

```text
cargo fmt --check: pass
cargo clippy --all-targets: pass
cargo test: pass, 60 library tests + 2 integration tests
smoke-test: ok = true, issues = []
full replay:
  replay_start_ts = 2025-06-16T02:30:00+00:00
  replay_end_ts   = 2026-07-08T05:30:00+00:00
  trade_count     = 291
  trend_trades    = 107
  mii_trades      = 184
  preempts        = 3
  cumulative_ret  = 695.9313992006354
  max_drawdown    = -0.27849173860427656
  win_rate        = 0.8281786941580757
```

## Boundary

This implements the code path for continuous dry-run and a disabled small live pilot, but it is not an operator approval to start live. Before setting `enabled = true`, the user must provide dedicated subaccount API env vars, confirm the subaccount balance size that controls pilot notional, and explicitly approve activation. The first production step should still be dry-run observation and live-readiness review of runtime logs/fills before real orders.
