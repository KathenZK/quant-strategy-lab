---
schema_version: "1.0"
spec_role: lab_handoff
family_id: BIN-15M-AS6S
main_status: dry-run
spec_status: active
implementations:
  - strategy_id: BIN-15M-AS6S-V6-NP
    runner_kind: asset_specific_six_selector_v6_mark_joint_np
    peer_spec: crates/quant-runner/src/runner/strategies/asset_specific_six_selector_v6_mark_joint_state/BIN-15M-AS6S-V6-NP-SPEC.md
  - strategy_id: BIN-15M-AS6S-V6-SBP
    runner_kind: asset_specific_six_selector_v6_mark_joint_preemptive
    peer_spec: crates/quant-runner/src/runner/strategies/asset_specific_six_selector_v6_mark_joint_state/BIN-15M-AS6S-V6-SBP-SPEC.md
manifest_instance_ids:
  - bin-15m-as6s-v6-mark-np-dry-run
  - bin-15m-as6s-v6-mark-preemptive-dry-run
approval_level_max: dry_run
overlays:
  - handoff
---

# 六币资产专属 V6 Mark 联合状态 Runner 草案

策略状态：`dry-run / not live-ready`。2026-07-15 经用户明确
授权，两条冻结路线均写入 active governance manifest 并启用持续 `dry-run`。
本规格不授权 testnet 或 `live`，也不改变未来 OOS 的禁改禁看边界。

## 固定身份

| 路线 | 策略 ID | Runner kind | 实例 |
| --- | --- | --- | --- |
| 不抢占 | `BIN-15M-AS6S-V6-NP` | `asset_specific_six_selector_v6_mark_joint_np` | `bin-15m-as6s-v6-mark-np-dry-run` |
| 强突破抢占 | `BIN-15M-AS6S-V6-SBP` | `asset_specific_six_selector_v6_mark_joint_preemptive` | `bin-15m-as6s-v6-mark-preemptive-dry-run` |

- 市场：Binance USD-M perpetual。
- 资产：BTC、ETH、SOL、BNB、TRX、HYPE，多空双向。
- 账户：全局单仓、允许空仓、scale `0.75`、最大 allocation `2.25`。
- 时钟：15 分钟闭合 K 推进；1 小时腿只消费完整闭合 1 小时 K。
- 成本：fee `0.001/fill`、基础 adverse slippage `0.0004/fill`；funding 按实际
  半开持仓区间累计。
- 版本参数唯一事实源：
  [`binance_as6s_v6_mark_joint_future_oos_freeze_2026-07-15.json`](../artifacts/binance_as6s_v6_mark_joint_future_oos_freeze_2026-07-15.json)。

## 路由状态机

共同规则：未获账户仓位的候选立即丢弃，不排队、不创建虚拟持仓、不写
cooldown；只有统一执行核确认 `Opened` 后才创建 active sleeve，确认 `Closed`
后才写真实 cooldown；同一平仓时间戳不重入。

不抢占路线持仓期间不接受任何新候选。强突破路线只允许不同 symbol 的 breakout
候选抢占，并必须同时满足 `strength >= 0.75`、比当前腿高至少 `0.05`、当前仓位
已持有至少 1 小时。抢占必须输出显式 `Replace`，执行时序为 `AfterFlat`；重启时
先恢复 pending replacement，禁止旧仓未平即开新仓。

## Mark 保护和退出

- 保护触发源为 Binance mark-price，订单保护类型为 `MarkPriceMarket`。
- 同一保护 bar 同时触发 stop/target 时 stop 优先；跳空按同 bar trade open，
  非跳空按冻结的 mark-to-trade 基差映射语义。
- 1 小时腿也逐根 15 分钟 mark K 检查保护，不能等待 1 小时 K 收盘。
- trailing 只在策略闭合 K 更新，并从下一保护 K 生效；交易所更新必须先确认
  新 stop 再撤旧 stop。
- mark 缺失时不得以 trade OHLC 代替。已有仓位应保留并 fail closed，等待保护、
  平仓或恢复；不得因依赖缺失增加风险。

## 持久化与恢复

策略 envelope 至少持久化：route、active sleeve、entry strength、pending entry、
pending replacement、各腿 cooldown、最后消费 K、1 小时 due-open 防重标记和
trailing 水位。订单、成交、实际仓位和保护单由统一执行核持久化。重启恢复必须
先对账交易所事实，再恢复策略状态；持仓 symbol 不得回落为实例默认 BTC。

## 已通过门禁

- 15 条腿 × 3 个历史检查，共 45 个信号与完整退出逐字段一致。
- 不抢占 `1486` 个候选、`634/634` 路由一致；强突破抢占 `1298` 个候选、
  `568/568` 路由一致。
- fixture SHA-256、CLI 回放、禁用实例 smoke、失败注入、完整测试和 clippy 证据见
  [`binance-as6s-v6-mark-joint-runner-2026-07-15.md`](../runner-tracking/binance-as6s-v6-mark-joint-runner-2026-07-15.md)。

## Dry-run 运行边界

1. 两个实例必须使用独立 state directory，账本按实例名和策略 ID 分账；不得把
   两条路线合并成一个虚拟账户或互相净额。
2. 当前只授权持续 `dry-run`，用于积累 forward mark 保护、部分成交、撤单
   outcome-unknown 和重启恢复证据。
3. 锁定未来 OOS 到期后一次性揭示，两条路线分别满足冻结硬门槛后，才可形成
   新的 promotion 决策；在此之前不得启用 testnet 或 `live`。
