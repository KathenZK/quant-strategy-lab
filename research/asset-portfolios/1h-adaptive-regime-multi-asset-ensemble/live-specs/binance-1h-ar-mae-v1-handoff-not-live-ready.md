---
schema_version: "1.0"
spec_role: lab_handoff
strategy_id: BIN-1H-AR-MAE-V1
family_id: BIN-1H-AR-MAE
main_status: dry-run
runner_kind: six_asset_ensemble
spec_status: active
peer_spec: crates/quant-runner/src/runner/strategies/six_asset_ensemble/BIN-1H-AR-MAE-V1-SPEC.md
manifest_instance_ids:
  - six-asset-ensemble-dry-run
approval_level_max: dry_run
---

# BIN-1H-AR-MAE-V1 Runner Handoff

状态：`dry-run / not live-ready`；manifest 已启用，live disabled。

- Exchange / market：Binance USD-M Futures。
- Assets / timeframe：六资产组合 / `1h`。
- Runner kind：`six_asset_ensemble`。
- Runtime：组合级严格单仓；Driver 声明六资产 K 线、mark 和 funding 依赖，
  dispatcher 统一构建 multi-market snapshot。不得按占位
  `BTC/USDT:USDT` 进入普通单标的共享行情组。
- Funding：空仓时任一 sleeve funding 获取失败必须阻止新入场；已有持仓仍须
  执行止损、止盈和 timeout，若 active sleeve funding 暂时不可得，则本次
  平仓的 net PnL 保持未知，不得静默按零 funding 记账。
- 持续 dry-run 是观测用逐 K 联合状态机，与 strict replay 存在已登记差异：
  mark-price 入场、asset 级 cooldown、timeout open 优先级。不得用持续
  dry-run 逐笔结果替代 strict replay parity。
- 完整参数、数据窗口、费用、funding、closed-bar 和 replay 口径以
  [`BIN-1H-AR-MAE-V1-SPEC.md`](file:///Users/ZK/OpenCode/quant-runner/crates/quant-runner/src/runner/strategies/six_asset_ensemble/BIN-1H-AR-MAE-V1-SPEC.md)
  为准。
- 现有逐笔 parity 只支持保持 dry-run；任何 live 提案都必须新开决策并修改
  manifest approval，当前 Runner 仍有代码级 live 拒绝。

## 统一 execution / venue 契约（2026-07-12 代码迁移）

- V1 的持续 dry-run 必须通过 symbol-explicit simulated venue 走完整 entry/exit
  order lifecycle；每个候选订单携带 sleeve 的真实 symbol，不能把 TOML placeholder
  当成实际合约。
- dry-run venue 独立持久化到
  `state/<instance>/simulated_venue.json`，并与平台唯一 execution 状态机共同实现稳定
  client ID、submit 前持久化、`pending/tracked`、按 fill 建仓、保护单、撤单、
  reconcile、fail-closed 与 platform ledger。
- 平台 live venue 是 Binance REST + User Data Stream，但 V1 继续 `DryRunOnly`，
  Runner 的 live 拒绝和 manifest approval 边界不变。
- `platform.execution.enabled` 与 live V1 fallback 已删除；不得通过旧开关或旧 executor
  绕开 `DryRunOnly`。
- strict replay/parity 与 simulated venue 隔离，不读取或改写 venue state；既有
  `371/371` 零误差结果应保持不变。
- 统一 execution 已于 `2026-07-13T04:25Z` 部署，原 HYPE long 持仓完成
  symbol-explicit venue 迁移并保持 health=`ok`。V1 的组合定义、promotion、
  parity 与 live-readiness 均不变。实现补记见
  [runner tracking](../runner-tracking/binance-1h-ar-mae-v1-runner-status.md)。
- 稳定性补充契约（Runner `e69589f`，已于 `2026-07-13 21:02 CST`
  部署 dry-run）：任一资产 transient 数据缺失时，
  不得用残缺 universe 开新仓；已有仓位必须继续止损/平仓维护并重试缺失依赖。
  multi-market Driver bundle 的失败不得终止同 service 的其他策略。该契约不授权 V1 live。

```toml
name = "six-asset-ensemble-dry-run"
kind = "six_asset_ensemble"
mode = "dry_run"
symbol = "BTC/USDT:USDT"
timeframe = "1h"
state_dir = "/home/admin/quant-runner/state/six-asset-ensemble-dry-run"
warmup_bars = 1500
dry_run_notional_usdt = 10.0
```

## Runner 实现绑定（2026-07-14，未部署）

V1 runtime 已统一为 multi-market `StrategyDriver`。六组 `MarketRequirement` 驱动
dispatcher 构建 candles/mark/funding 完整快照；任一依赖缺失时禁止新开仓。
sleeve/active-position/cooldown 私有状态保存到 versioned
`StrategyStateEnvelope`，动态 symbol 订单仍走统一 execution kernel。策略通过
`inventory` 自注册，不再存在 self-managed runtime 分支。该变更不替代
`371/371` parity，也不改变 `dry-run / not live-ready`。
symbol/side/allocation 变化必须显式 `Replace` 并按 persisted `AfterFlat`
close-confirm-open；重启时从 `pending_replacement` 续做，不提供隐式仓内 resize。
