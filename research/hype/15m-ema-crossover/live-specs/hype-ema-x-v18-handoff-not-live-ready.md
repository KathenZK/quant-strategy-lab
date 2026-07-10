---
spec_role: lab_handoff
strategy_id: HYPE-EMA-X-V18
family_id: HYPE-EMA-X
runner_kind: hype_ema_x
spec_status: active
peer_spec: crates/quant-runner/src/runner/strategies/hype_ema_x/HYPE-EMA-X-V18-SPEC.md
manifest_instance_ids:
  - hype-ema-x-dry-run
  - hype-ema-x-live
approval_level_max: dry_run
---

# HYPE-EMA-X-V18 Runner Handoff

状态：`dry-run / forward-test required / not live-ready`。

- Exchange / market：Binance USD-M Futures。
- Symbol / timeframe：`HYPE/USDT:USDT` / `15m`。
- Closed-bar rule：只使用已闭合 15m K；信号确认后下一根 open 执行。
- Runner kind：`hype_ema_x`。
- Runner 参数、状态机、费用、滑点、warmup 和恢复字段以
  [`HYPE-EMA-X-V18-SPEC.md`](file:///Users/ZK/OpenCode/quant-runner/crates/quant-runner/src/runner/strategies/hype_ema_x/HYPE-EMA-X-V18-SPEC.md)
  为实现真源；研究冻结参数见
  [`specs/hype-ema-x-v18-baseline-spec.md`](../specs/hype-ema-x-v18-baseline-spec.md)。
- TOML 只声明实例身份、账户、mode、state path、warmup 和 dry-run notional；
  alpha 参数不得放进 TOML。
- Live blockers：标准 parity、dated runner observation、真实费用/滑点、
  保护单/重启恢复、missing-bar 与 kill-switch 验收。

```toml
name = "hype-ema-x-dry-run"
kind = "hype_ema_x"
mode = "dry_run"
symbol = "HYPE/USDT:USDT"
timeframe = "15m"
state_dir = "/home/admin/quant-runner/state/hype-ema-x-dry-run"
warmup_bars = 5000
dry_run_notional_usdt = 10.0
```
