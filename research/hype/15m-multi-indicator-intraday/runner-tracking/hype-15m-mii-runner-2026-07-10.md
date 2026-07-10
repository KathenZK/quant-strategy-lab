# HYPE-15M-MII V1.4A dry-run deployment — 2026-07-10

## Status

`HYPE-15M-MII-V1.4A` was deployed to the existing `hype-mii-dry-run`
instance at `2026-07-10T07:13:16Z`. The first post-deployment 15m cycle was
healthy. It remains not live-ready.

## Prepared runner configuration

- Runner: `quant-runner`, `kind=hype_mii`, `mode=dry_run`.
- Instance: `hype-mii-dry-run` (instance name intentionally has no version).
- Identity: `HYPE-15M-MII-V1.4A`.
- Market: Binance USD-M `HYPEUSDT`, `15m`, closed candles only.
- Sizing: `dry_run_notional_usdt=10`, `exposure=2.5`, `leverage=3`,
  `margin_mode=isolated`.
- State: existing `/home/admin/quant-runner/state/hype-mii-dry-run`; retained
  because the prior V1.3 instance had never opened a position.
- Fixed strategy parameters: `min_rvol96=0.85`, `tp_atr_mult=1.40`,
  `sl_atr_mult=3.0`, `timeout_bars=24`, fee `0.001`/fill, slippage
  `0.0004`/fill.
- Live boundary: the runner rejects this identity in `live` mode.

## Local verification

Source workspace: `/Users/ZK/OpenCode/quant-runner`.

- `cargo fmt --check`: passed.
- `cargo test -p quant-runner`: passed (`63` library tests, `2` integration
  tests).
- `smoke-test --name hype-mii-dry-run`: passed.
- Binance public closed-Kline smoke replay, `2500` bars: `11` signals and
  `10` simulated trades; replay emitted the required V1.4A parameter snapshot.

The same recent 2500-bar window was also checked against the Python research
engine: both selected the same 10 trades with matching entry/exit timestamps,
side, and exit reason. Rust applies its configured fill slippage at the price
level, so fill prices are intentionally not raw K+1 opens.

## Deployment evidence

- Initial V1.4A deployment commit:
  `a52562ee057c19f28541a5ccc8ff5522d31efefc`
  (implementation commit `7e30d6d` plus Linux artifact workflow).
- Initial build source: GitHub Actions run `29075757922`, native
  `x86_64-unknown-linux-gnu`; no compilation occurred on the trading server.
- Initial artifact SHA-256:
  `db7f446b835a9d39d25670d2e510f26f6c2d107bdf3f843c1592e8ce98e6a480`.
- Current deployed commit: `61cb32a01944efe9011167cbb9ab0bef6fcfccf2`.
- Current build source: GitHub Actions run `29076613028`; artifact SHA-256
  `f76cfcffa3908c25d2b29913895937819c313fc34487e1efcf3a665f66bb5380`.
- Current dry-run config SHA-256:
  `444cc8407e61e5ba3d23a692d5ed2700795238027042d01d336dace832201a1d`.
- Source commands/evidence: systemd status/journal, platform SQLite
  `strategy_instances`, `strategy_health`, `events`, and installed-binary
  `replay-dry-run --limit 300` parameter snapshot.
- Only `quant-runner-dryrun.service` was restarted. The live service remained
  active on its existing PID.
- Pre-restart MII state: flat, zero historical/open trades, no prior signal;
  existing state path retained.
- First post-deployment cycle: runner start
  `2026-07-10T07:13:16Z`; processed closed signal bar
  `2026-07-10T07:00:00Z` at `2026-07-10T07:15:03Z`; event `no_signal`;
  `strategy_health.status=ok`, `position_open=0`.
- Installed parameter snapshot: internal identity `HYPE-15M-MII-V1.4A`,
  `min_rvol96=0.85`, `tp_atr_mult=1.40`, `sl_atr_mult=3.0`,
  `timeout_bars=24`.
- No warning-or-higher journal entries appeared after restart. All other
  strategy health rows remained `ok`.
- At `2026-07-10T07:31Z`, dry-run startup notification support was deployed.
  `quant-runner-dryrun.service` restarted successfully and sent
  `QuantRunner dry-run 服务启动` through the configured DingTalk webhook.
  Dry-run trade notifications and its daily-summary scheduler remain disabled;
  the live service stayed on its existing PID. No warning-or-higher journal
  entries followed the notification restart.

## Observation gate

No V1.4A runtime open, close, fill, fee, funding-boundary, slippage, or order
IDs exist yet. The first actual trade must be reconciled against Python K+1/K+2
using signal/bar timestamps, fill proxy, side, quantity/notional, bracket,
exit reason, fees, and stable ledger event/trade IDs before any keep/adjust
decision. Current conclusion: continue small dry-run observation; no live
promotion.
