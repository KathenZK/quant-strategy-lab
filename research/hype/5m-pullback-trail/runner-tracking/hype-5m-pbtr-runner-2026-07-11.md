# HYPE-5M-PBTR-V6.2.1 Execution Governance Follow-up 2026-07-11

## Scope

- Runner kind / mode: `hype_pullback` / `live tiny-live-pilot`
- Source config: `configs/live.toml`
- Deployment: not performed in this change
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

## Validation

- Local Rust fmt, strict Clippy and all unit/integration tests: pass.
- No real Binance order was submitted.
- Existing production service remains unchanged until a separate artifact-based
  deployment and flat-position preflight.

## Decision

`adjust complete in source / deployment pending`. Do not increase funds before
post-deploy user-stream, reconcile and first-fill checks are recorded.
