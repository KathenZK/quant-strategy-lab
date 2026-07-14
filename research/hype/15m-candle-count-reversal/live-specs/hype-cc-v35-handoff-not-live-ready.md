---
spec_role: lab_handoff
strategy_id: HYPE-CANDLE-COUNT-V35
family_id: HYPE-CC
runner_kind: hype_candle_count
spec_status: active
peer_spec: crates/quant-runner/src/runner/strategies/hype_candle_count/HYPE-CANDLE-COUNT-V35-SPEC.md
manifest_instance_ids:
  - hype-candle-count-v35-dry-run
approval_level_max: dry_run
---

# HYPE-CANDLE-COUNT-V35 Runner Handoff

状态：`dry-run / forward-test required / not live-ready`。历史 live
underperformance 不因当前 dry-run 重新观察而失效。

- Exchange / market：Binance USD-M Futures。
- Symbol / timeframe：`HYPE/USDT:USDT` / `15m`。
- Runner kind：`hype_candle_count`。
- Closed-bar rule：信号只用闭合 K，下一根 open 执行；mark K、funding 和
  protection order 行为必须单独对账。
- Runner 实现规格：
  [`HYPE-CANDLE-COUNT-V35-SPEC.md`](file:///Users/ZK/OpenCode/quant-runner/crates/quant-runner/src/runner/strategies/hype_candle_count/HYPE-CANDLE-COUNT-V35-SPEC.md)。
- 研究参数规格：
  [`specs/hype-v35-reproducible-params.md`](../specs/hype-v35-reproducible-params.md)。
- Live blockers：标准 parity、dated runner report、历史 underperformance
  复核、保护单/重启恢复、费用/滑点/funding 和平台安全闸验收。

## 统一 execution / venue 契约（2026-07-12 代码迁移）

- V35 dry-run 与任何未来 live 必须走唯一 execution 状态机：稳定 client ID、
  submit 前持久化、`pending/tracked`、按 fill 建仓、保护单、entry/exit order
  lifecycle、reconcile、fail-closed 与 platform ledger。
- live venue 是 Binance REST + User Data Stream；dry-run venue 是实例独立的
  `state/<instance>/simulated_venue.json`，不得由 candle-count runner 直接改仓。
- `platform.execution.enabled` 与 live V1 fallback 已删除；旧 executor 不再是回退。
- strict replay/parity 保持隔离，本次迁移不应改变既有 replay 结果。
- 统一 execution 已于 `2026-07-13T04:25Z` 部署，原 short 持仓完成
  simulated venue + TP/SL 迁移并保持 health=`ok`。V35 参数、历史
  underperformance、promotion、parity 与 live-readiness 均不变。实现补记见
  [runner tracking](../runner-tracking/hype-cc-runner-2026-07-10.md)。
- 稳定性补充契约（Runner `e69589f`，已于 `2026-07-13 21:02 CST`
  部署 dry-run）：transient dependency 只关闭新入场，
  不得停止 candle-count 已有仓位、保护单、撤单或平仓；单 group 故障不得终止
  兄弟策略。

```toml
name = "hype-candle-count-v35-dry-run"
kind = "hype_candle_count"
mode = "dry_run"
symbol = "HYPE/USDT:USDT"
timeframe = "15m"
state_dir = "/home/admin/quant-runner/state/hype-candle-count-v35-dry-run"
warmup_bars = 5000
dry_run_notional_usdt = 10.0
```

## Runner 实现绑定（2026-07-14，未部署）

Candle-Count runtime 已统一为 `StrategyDriver`。risk multiplier、cooldown 和
early-exit 状态由 Driver 保存到 versioned `StrategyStateEnvelope`；mark/funding
由声明式 `MarketRequirement` 提供，mark stop/take 使用 touch-only bar 口径。
订单、保护、reconcile 与 ledger 仍由统一 execution kernel 执行。该变更不修改
V35 参数、state path、历史 underperformance blocker 或 live 禁用结论。
新仓 target 只能使用 `NextOpen`；allocation/side 变化必须显式 `Replace` 并按
persisted `AfterFlat` close-confirm-open，不提供隐式仓内 resize。
