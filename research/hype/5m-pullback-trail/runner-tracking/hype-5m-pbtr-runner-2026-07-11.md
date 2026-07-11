# HYPE-5M-PBTR-V6.2.1 Execution Governance Follow-up 2026-07-11

## Scope

- Runner kind / mode: `hype_pullback` / `live tiny-live-pilot`
- Source config: `configs/live.toml`
- Deployment: live-only production cutover completed at 2026-07-11 16:14 CST
- Runtime trade/fill export: not collected

## Completed safeguards

- Added `live_execution_sim.rs` fault scenarios for accepted-timeout idempotency,
  partial protection fills, sibling cancellation, protection/emergency failures,
  kill between entry and arm, unfilled orphan cancellation and user-stream loss.
- Entry pending now remains durable until `PositionState` is persisted.
- Startup automatically cancels an unfilled orphan entry or reduce-only flattens
  an orphan exchange position, then remains fail-closed for review.
- Fallback critical JSONL automatically drains into the central outbox; outbox
  delivery status, retry and backlog alerts are implemented.
- TB-MII fail-closed, manual halt, stale health and shared-group graceful shutdown
  now emit durable/notification evidence.
- `connect_timeout` and atomic binary-before-systemd-unit installation are defined.
- Source `configs/live.toml` now stages execution v2 + private user stream enabled.

## Deployment evidence

- Local Rust fmt, strict Clippy and all unit/integration tests: pass.
- Lab main: `bb8586a`; Runner main: `712b3e9`.
- GitHub Actions run: `29145511766`; artifact:
  `quant-runner-linux-x86_64-712b3e96e630983bbc1e72c6d31f3a78788726bb`.
- Artifact / installed binary SHA-256:
  `3cf36d61dfdb1cb8930a924614b00108323b9d00a49d05c42cb3a5c3c04f8487`.
- Preflight: live local/exchange state flat, no open orders, no open live ledger
  trade; old service smoke-test `ok=true`.
- Atomic install order: new ELF binary first, live unit second, daemon reload,
  restart only `quant-runner-live.service`.
- Dry-run was not restarted; its PID/unit remained unchanged.
- Post-cutover: live `Type=notify`, `WatchdogSec=120`, PID `763218`,
  `NRestarts=0`, health `ok`, `position_open=0`.
- Ledger emitted `runner_started`, `binance_user_stream_connected`, then a healthy
  cycle. No warning-or-higher journal entries were observed.
- The same PID remained active with `NRestarts=0` after a full watchdog interval.
- No real Binance order was submitted because the signal window remained flat.

## Decision

`keep tiny-live-pilot / execution v2 deployed and healthy`. Do not increase funds.
The next mandatory evidence is the first real signal/order/fill reconciliation,
including stable client IDs, protection orders, fees, slippage and user-stream
timestamps.
