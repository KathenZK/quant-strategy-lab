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

## 统一 execution / venue 契约（2026-07-12 代码迁移）

- V18 的 dry-run 与任何未来 live 必须走唯一 execution 状态机：稳定 client ID、
  submit 前持久化、`pending/tracked`、按 fill 建仓、保护单、exit order、
  reconcile、fail-closed 与 platform ledger。
- live venue 是 Binance REST + User Data Stream；dry-run venue 是实例独立的
  `state/<instance>/simulated_venue.json`，不得由 EMA-X runner 直接模拟或改写仓位。
- `platform.execution.enabled` 与 live V1 fallback 已删除；旧 execution 不能作为
  兼容回退。
- strict replay/parity 与 venue/runtime 保持隔离，本次迁移不应改变既有结果。
- 统一 execution 已于 `2026-07-13T04:25Z` 部署到 dry-run service；本实例 flat、
  health=`ok`，没有新增 EMA-X fill。V18 的 alpha、状态机信号规则、promotion、
  parity 与 live-readiness 均不变。实现补记见
  [runner tracking](../runner-tracking/hype-ema-x-runner-2026-07-10.md)。
- 稳定性补充契约（Runner `e69589f`，已于 `2026-07-13 21:02 CST`
  部署 dry-run）：transient dependency 只关闭新入场，
  不得停止 EMA-X 已有仓位维护、撤单、保护或平仓；单 group 故障不得终止兄弟策略。

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
