# HYPE-5M-PBTR-V6.2.1 Execution Governance 2026-07-10

## Scope

- Runner kind: `hype_pullback`
- Runtime modes affected in source: dry-run and disabled-by-default execution v2 live path
- Deployment: not performed
- Live service during development: existing binary/config kept running

## Implemented evidence

- Stable idempotent client order IDs and `origClientOrderId` recovery.
- Persist-before-submit pending state and startup fail-closed reconciliation.
- Protection orders use actual `executedQty` / exchange position quantity.
- Protection failure requires confirmed emergency flat; failure remains persisted.
- Binance private order/account event stream plus REST reconciliation fallback.
- Partial protection fills cancel the sibling order and re-arm the residual position.
- Manual halt, critical outbox, HTTP timeout/clock/recvWindow/rate/min-notional
  guards, graceful shutdown and systemd watchdog support.

## Local verification

- Rust unit/integration tests, format and strict Clippy: pass.
- Governance lock/spec gates: pass.
- Real Binance order fault injection: not performed.
- Live execution v2 activation: not performed.

## Decision

`keep` the existing tiny pilot without increasing funds; do not switch to execution
v2 until an exchange-flat maintenance window and controlled preflight are available.
