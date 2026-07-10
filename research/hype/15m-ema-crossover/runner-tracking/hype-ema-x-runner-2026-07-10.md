# HYPE-EMA-X-V18 Runner Governance 2026-07-10

- Kind / mode: `hype_ema_x` / dry-run; live remains disabled.
- Runner config: `configs/dryrun.toml`, notional `10 USDT`, existing state path.
- Observation window: source-level/offline governance validation only.
- Trades/fills: no runtime trade export was collected in this change.
- Incidents: none observed; no deployment was performed.

Implemented shared execution safeguards: stable live order identity, pending recovery,
actual fill quantity, confirmed emergency flatten, private order stream/REST
reconciliation, manual halt, critical outbox, exchange request guards, graceful
shutdown and stale-health watchdog. EMA-X live exits no longer require a future REST
K-line open.

Parity remains `PENDING`; the offline strategy baseline is not a substitute for
Python/Rust full-window trade-path parity.

Decision: `keep dry-run / do not enable live`.
