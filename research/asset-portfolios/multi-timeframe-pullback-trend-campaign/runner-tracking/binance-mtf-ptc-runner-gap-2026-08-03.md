# BIN-MTF-PTC Runner 能力差距

## 状态

本家族未通过历史门禁，因此本文件只是能力审计，不是 runner handoff、live spec 或开发授权。用户已明确本轮不需要实现 live/dry-run 代码。

审计对象：`/Users/ZK/OpenCode/quant-runner` 当前工作树，2026-08-03 只读检查；未修改 sibling repo。

## 已具备的公共能力

- `StrategyDriver` 可声明多 symbol/timeframe、mark/funding 数据依赖，并获得原子 `MarketSnapshot`。
- Driver 有版本化私有状态、逐步 migration、snapshot/restore；可保存 continuation model state、pending candidate 和 campaign metadata。
- `TargetPosition` 支持 next-open timing、signed allocation、显式 stop/timeout、3x allocation validation。
- execution kernel 已具备稳定 client order id、pending entry/exit/replacement、venue reconcile、保护缺失 fail-closed、partial protection fill 的残余仓位补保护、中心 ledger 与通知。
- funding events 可送入 driver；当前 position/order/protection mismatch 有 reconcile 路径。

代码入口：[Driver contract](../../../../../quant-runner/crates/quant-runner/src/runner/strategies/driver.rs) · [Execution state](../../../../../quant-runner/crates/quant-runner/src/runner/trading/state.rs) · [Driver runtime](../../../../../quant-runner/crates/quant-runner/src/runner/trading/runner/driver_runtime.rs)

## 阻断真实 Campaign parity 的差距

### 1. 单一 PositionState，不能表达独立 lots

当前 `PositionState` 只有一个 aggregate `quantity`、一个 `entry_price`、一个 `stop_price` 和一组保护单 id。研究状态机需要 Probe/Add-1/Add-2/Add-3 分别保存 fill、quantity、stop、fee、funding attribution、attempt identity 和 LIFO 顺序。

现有 partial-protection-fill 逻辑只处理交易所保护单部分成交后的残余 aggregate position，不等于策略可主动管理多 lot/多 stop。

### 2. 同方向 allocation 变化被强制 Close → Flat → Reopen

当前 held-position Driver decision 只有：

- 同 symbol、同 side、同 allocation：允许 protection update；
- allocation/side/symbol 有变化：必须显式 `Replace`，先整仓 close，再确认 flat 后 reopen。

因此同方向 add、partial de-risk、LIFO risk trim 都会被错误映射成整仓换手，无法复现研究账本的价格、费用、funding、持有年龄和独立 stop。

### 3. 保护内核只有 aggregate stop

Campaign 需要每个 lot 独立 stop，并允许在 +2R 后只收紧旧 lot stop。当前 kernel protection 绑定 aggregate quantity；即使 Driver 私有状态保存 lots，execution/reconcile 也无法验证“每个 lot 的 stop quantity 总和 = venue position quantity”。

### 4. Pending order 模型不支持多阶段 pullback plan

当前 execution safety 有单一 pending entry、pending exit 和 replacement；策略私有状态可以记 pending，但 runtime 没有原生的：

- candidate → 24h await pullback；
- restart 后 next-open entry；
- 每 layer 两次 attempt；
- pending add 与 Probe 的不同 role/generation；
- 同一 campaign 多个可恢复的 add/trim order。

若只存在 Driver JSON 而 venue order/quantity generation 没有一一对应，重启后无法安全确定某层是否已成交。

### 5. Live entry 目前固定 market order

`TargetPosition.execution_price` 在 live 只作为 sizing reference；实际入口调用 `market_entry`。V2 限价机制虽已研究失败，但若未来后继策略需要 causal limit retest，当前接口不能直接发可恢复、会过期的 entry limit order。

### 6. 风险视图不足

`ExecutionView` 暴露 aggregate position，不提供：

- account/equity snapshot 与 liquidation equity；
- lot-level projected stop-out equity；
- funding 后 operational/hard risk；
- exchange precision 后每层实际 risk；
- current margin/leverage contribution。

Driver 无法独立证明 `operational<=0.9% / hard<=1% / leverage<=3x` 并安全决定 partial add/trim。

### 7. Ledger 需要 lot/action 级扩展

当前 trade open/close ledger 适合 aggregate trade。Campaign parity 还需要 immutable action records：score、plan、expiry、eligibility、add attempt、lot fill、lot stop replacement、partial trim、funding allocation、projected risk before/after、idempotency key。

## 若未来某个后继版本通过门禁，最小扩展顺序

1. 新增平台级 `CampaignPosition` / `LotState` schema，而不是把 lots 仅藏在 strategy JSON；
2. 新增 same-direction `Resize` decision，明确 delta quantity、role、lot id、timing 和保护；
3. execution kernel 支持多 stop 或明确的 strategy-managed stop router，并做 stop quantity reconciliation；
4. pending resize/partial-exit 使用稳定 client ids 和 generation，覆盖 timeout-after-acceptance、partial fill、restart recovery；
5. Driver context 加入 account/equity/margin/risk view；统一计算 projected stop-out risk；
6. funding settlement 后在同一 cycle 运行 LIFO risk maintenance；
7. ledger 增加 campaign/lot/action 表或等价不可变事件；
8. 建立 Python research ↔ Rust replay 逐 action 对拍：candidate、score、plan、fill、stop、funding、risk、equity 全序列一致；
9. fault injection：entry 后保护前 kill、add partial fill kill、stop replacement kill、funding 后 trim kill、venue/local quantity mismatch；
10. 只有 parity 与 fresh prospective 同时通过，才写 live spec。

## 当前决定

无需也不应扩展 runner：策略本身尚未通过收益、压力与集中度门禁。先为失败策略建设多 lot execution 会把研究问题变成工程投入，不能提高 alpha。
