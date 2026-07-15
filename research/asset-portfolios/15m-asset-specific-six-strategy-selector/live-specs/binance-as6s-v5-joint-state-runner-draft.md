---
spec_role: lab_handoff
strategy_id: BIN-15M-AS6S-V5-JOINT-NP
family_id: BIN-15M-AS6S
runner_kind: asset_specific_six_selector_v5_joint_state
spec_status: draft
peer_spec: crates/quant-runner/src/runner/strategies/asset_specific_six_selector_v5_joint_state/BIN-15M-AS6S-V5-JOINT-NP-SPEC.md
manifest_instance_ids: []
approval_level_max: disabled
---

# 六币资产专属 V5 联合状态 Runner 草案

状态：`frozen observation / not registered / not promoted / not live-ready`。
本草案只授权独立 Runner 模块和离线逐笔对拍，不授权新增或启用 dry-run/live
实例，不改变任何既有策略身份。

## 固定身份与边界

- 策略 ID：`BIN-15M-AS6S-V5-JOINT-NP`。
- Runner kind：`asset_specific_six_selector_v5_joint_state`。
- 市场：Binance USD-M perpetual。
- 币种：BTC、ETH、SOL、BNB、TRX、HYPE。
- 决策时钟：六币闭合 `15m` K 共同推进；同时读取六币闭合 `1h` K。
- 路线：第一实现只复刻收益更高的 `nonpreemptive` 路线；
  `strong-breakout-preemptive` 保留为研究比较，不得静默混入。
- 账户：同一时刻最多一笔仓位，允许空仓，持仓期间其他信号直接丢弃。
- 入场：信号 K 闭合后 `K+1` 下一根 open；`K+2` 只作为压力测试。
- 成本：fee `0.001/fill`，adverse slippage `0.0004/fill`。
- 账户缩放：`0.40 × sleeve exposure`，最大 allocation `1.20`。

## 成分机制

V5 固定 15 条资产专属腿，不要求每个币机械地凑齐趋势、突破、反转：

- 9 条原生 `15m`：HYPE clean-RSI；BNB breakout；ETH breakout/trend；
  HYPE breakout/reversal；SOL breakout/reversal/trend。
- 6 条原生 `1h`：BNB wick-reject、BTC keltner-break、ETH RSI-reversal、
  HYPE DI-cross、SOL donchian-break、TRX MACD-flip。

完整参数、quality、exposure、strength 公式和市场依赖以冻结执行契约
[`binance_as6s_v5_joint_state_execution_contract_2026-07-14.json`](../artifacts/binance_as6s_v5_joint_state_execution_contract_2026-07-14.json)
为唯一输入；Runner 不得从后续行情重新估计这些值。

## 联合状态语义

1. 每个闭合决策点仅从当前真实信号生成候选。
2. 排序键固定为 `strength desc, sleeve_id asc, symbol asc, side desc`，不得使用
   `exit_ts`、未来收益或持仓后才能知道的字段。
3. 未获账户仓位的信号立即丢弃，不排队，不创建虚拟持仓，不写 cooldown。
4. 只有执行层确认 `Opened` 后才创建唯一 active state。
5. 只有该真实持仓 `Closed` 后才允许写该腿冻结的显式 cooldown。
6. 平仓同一时间戳不得再次入场。
7. `1h` 信号只在该小时 K 刚闭合后的第一个 `15m` open 有效；持久化
   `last_due_open_ts_by_sleeve` 防止随后三个 15m 周期重复消费。

## Runner 实现门禁

- 新模块必须独立维护 joint state；可以复用既有 1h 纯特征/信号函数，但不得
  复用既有 `six_asset_ensemble` 的持仓和 cooldown 状态。
- 任一六币 15m/1h 必需 candle 缺失、过期或不对齐时禁止增加风险；已有仓位
  仍需 fail-safe 维护。
- 历史逐笔对拍继续用冻结 trade-OHLC 状态机；真实 Runtime 的退出状态由
  Driver 管理，但初始 stop/TP 和 trailing stop 必须作为交易所
  `MarkPriceMarket` 保护存在，二者不得再被等同为 `StrategyManaged` 裸仓。
- 常规周期、REST reconcile 和重启恢复必须先识别可归因的保护成交；持仓存在但
  stop/TP 缺失时按实际持仓 symbol 补挂，不能回落到实例默认 BTC symbol。
- 2026-07-15 已通过 ETH 多币种保护武装、mark 止损成交识别和重启后缺失保护
  重建测试；这解除实现缺口，不自动授权 dry-run 或 live。
- 离线对拍必须校验 sleeve、symbol、side、entry_ts、exit_ts、exit_reason 和净收益，
  并单独说明 mark-price dry-run 与 trade-OHLC strict replay 的边界。

截至 2026-07-15，45 个抽样信号、15 条腿各一笔完整退出和全 553 笔账户路由
已通过对拍；交易所 mark 保护与多币种重启恢复定向测试也已通过。证据见
[`binance_as6s_v5_joint_state_runner_parity_2026-07-15.json`](../artifacts/binance_as6s_v5_joint_state_runner_parity_2026-07-15.json)。
批准上限仍为 `disabled`：尚未完成持续 dry-run、真实订单生命周期 smoke、
trailing 更新失败注入/测试网审计与未来 OOS。成功的 trailing 更新路径已固定为
先挂新 stop、确认后撤旧 stop，TP 不变时保持原 TP。

## 冻结结果校验

`nonpreemptive/base` 全历史应为：`553` 笔、胜率 `85.1718%`、总收益
`+3280.1321%`、年化权益倍数 `5.8156x`、最大回撤 `-12.8570%`。
最近三个月应为：`81` 笔、胜率 `83.9506%`、收益 `+69.1924%`、最大回撤
`-7.8893%`。这些是已揭示历史诊断，不替代锁定未来 OOS。

最终未来 OOS 固定为 `[2026-07-14T09:00Z, 2026-10-14T09:00Z)`；窗口结束前
不得查看部分结果或据此调整 Runner 参数。
