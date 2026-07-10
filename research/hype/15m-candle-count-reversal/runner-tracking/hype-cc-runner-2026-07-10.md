# HYPE-CANDLE-COUNT-V35 Runner Governance 2026-07-10

- Kind / mode: `hype_candle_count` / dry-run; no live instance is approved.
- Runner config: `configs/dryrun.toml`, notional `10 USDT`, existing state path.
- Observation window: source-level/offline governance validation only.
- Trades/fills: no runtime trade export was collected in this change.
- Historical live underperformance remains a blocker.

Implemented shared execution safeguards: stable live order identity, pending recovery,
actual fill quantity, confirmed emergency flatten, private order stream/REST
reconciliation, manual halt, critical outbox, exchange request guards, graceful
shutdown and stale-health watchdog.

Parity remains `PENDING`; the offline strategy baseline and existing strict replay
tests do not replace a Lab-vs-Runner full-window path comparison.

Decision: `keep dry-run / do not enable live`.
