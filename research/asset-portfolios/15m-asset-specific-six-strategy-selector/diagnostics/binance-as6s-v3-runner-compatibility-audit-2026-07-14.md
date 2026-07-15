# 六币单币优先 V3 Runner 兼容性审计（2026-07-14）

## 结论

用户提出的方向是正确的：先在每个币上寻找适合其价格结构的高收益、可控回撤机制，再把通过稳健性审计的腿放入全局单仓位账户；组合层只负责资金占用与候选冲突，不能替代单腿质量。

V3 已按该方向重做，不再要求六币共用一套趋势、突破和反转模板。当前冻结观察包含 `15` 条资产专属腿，账户层结果已明显高于早期低回撤、低收益组合：

| 路径 | 全区间年化权益倍数 | 全区间胜率 | 全区间最大回撤 | 最近三个月收益 / 胜率 / 回撤 |
| --- | ---: | ---: | ---: | ---: |
| nonpreemptive | `5.91x` | `85.40%` | `-12.86%` | `+72.47% / 84.81% / -7.47%` |
| strong-breakout-preemptive | `4.59x` | `85.46%` | `-8.27%` | `+57.08% / 84.81% / -6.17%` |

这些指标仍是 frozen observation，不是上线结论。未来最终 OOS `[2026-07-14T09:00Z, 2026-10-14T09:00Z)` 尚未完成，V3 维持 `not registered / not promoted / not live-ready`。

现有 `quant-runner` 平台骨架能够承载 V3，但旧 `six_asset_ensemble` 不能通过改参数直接复用。V3 必须建立新的 `asset_specific_six_selector` Driver，并完成逐笔 runner replay 对账；当前不应修改旧 `BIN-1H-AR-MAE-V1` 的身份或实现。

## 当前冻结机制

| 币种 | V3 入选机制 |
| --- | --- |
| BTC | 1h Keltner breakout |
| ETH | 15m breakout、15m trend state、1h RSI reversal |
| SOL | 15m breakout、15m reversal、15m trend state、1h Donchian breakout |
| BNB | 15m breakout、1h wick reject |
| TRX | 1h MACD flip |
| HYPE | 15m Clean-RSI reversal、15m breakout、15m reversal、1h DI cross |

这不是“每个币强制三条腿”，而是“每个币广泛搜索后只保留成本后有效机制”。BTC 和 TRX 没有为了凑数强塞 15m 反转；HYPE、SOL、ETH 则保留了多个互补机制。

机器执行边界已固化在[执行契约](../artifacts/binance_as6s_v3_execution_contract_2026-07-14.json)，生成入口为[契约构建脚本](../scripts/build_binance_as6s_v3_execution_contract.py)。契约包含 15 条腿、两条路由、有效暴露、12 组市场依赖、混合周期去重规则、全局状态字段和 promotion 前逐笔对账门禁。

## Runner 能力对照

| V3 要求 | 当前 runner 能力 | 结论 |
| --- | --- | --- |
| 六币原子输入 | `StrategyDriver` 支持多个 `MarketRequirement` | 可复用 |
| 15m 决策时钟 + 1h 次级序列 | bundle 按最短周期唤醒，可同时拉不同 timeframe | 可复用，但 V3 需自行做 1h due-open 去重 |
| 下一根开盘入场 | `TargetPosition + TransitionTiming::NextOpen` | 可复用 |
| 全局同时最多一个仓位 | 单 Driver 的 `ExecutionView.position` 与账户拓扑可约束 | 可复用 |
| 强突破抢占 | `StrategyDecision::Replace + AfterFlat` | 可复用骨架，需审计双币连续成交偏差 |
| 逐腿止损、止盈、timeout、trailing | `ProtectionPlan` 与 Driver 持久化状态支持 | 可复用骨架，保护价格源仍需定口径 |
| 重启恢复 | versioned Driver state、交易所 reconciliation | 可复用 |
| 数据缺失 fail-closed | 多市场依赖缺失时禁止增仓和 Replace | 可复用 |
| 15 条异构信号引擎 | 当前只有旧 1h AR-MAE 统一引擎 | 缺失，必须实现 |
| V3 两条路由 replay 与冻结账逐笔一致 | 当前无 V3 replay | 缺失，promotion blocker |

参考的平台接口为 [StrategyDriver](../../../../../quant-runner/crates/quant-runner/src/runner/strategies/driver.rs)，旧六币骨架为 [six_asset_ensemble](../../../../../quant-runner/crates/quant-runner/src/runner/strategies/six_asset_ensemble/mod.rs)。旧模块登记为 `BIN-1H-AR-MAE-V1` 且 `DryRunOnly`，只能作为结构参考。

## 不能直接套旧六币模块的原因

### 1. 周期和机制不同

旧模块只有六币统一 `1h` 输入及同一种 AR-MAE 特征框架。V3 同时包含 15m Clean-RSI、15m breakout、15m trend state、15m reversal 和六条旧 1h 机制。信号计算、timeout bars、trailing 更新和候选到期时点都必须按腿的原生周期执行。

### 2. 1h 信号会在四个 15m 周期里重复出现

bundle 每 15 分钟唤醒时，最新闭合 1h K 在一小时内不变。如果只看“1h 最新信号是否非零”，同一信号会被重复提交。V3 Driver 必须持久化 `last_due_open_ts_by_sleeve`，只允许 1h 信号在该 1h K 闭合后的第一个 15m open 参与一次仲裁。

### 3. cooldown 必须按 sleeve，而不是按资产

同一个币可同时有多条独立腿。某条 ETH breakout 真实成交后的 cooldown 不应关闭 ETH trend state 或 ETH RSI reversal。状态键必须使用完整 `sleeve_id`；旧六币模块按 asset 保存 cooldown，不符合 V3。

### 4. 两条账户路线是不同策略实例

nonpreemptive 在持仓时丢弃全部新信号；preemptive 只接受“其他币 + breakout + strength 门槛 + margin + 最短持仓”挑战者。路由模式必须在实例启动时冻结，不能在运行中动态切换，也不能共用一个状态目录。

### 5. 旧模块的 StrategyManaged 保护不能直接用于实盘

旧 `six_asset_ensemble` 由 Driver 自己根据轮询到的 K 线判断 stop/target，`StrategyManaged` 不在交易所挂保护单。这也是旧模块保持 `DryRunOnly` 的重要边界。V3 若改用交易所 `MarkPriceMarket` 保护，触发价格源将从研究中的 trade OHLC 变为 mark price，必须先做 mark/trade 双路径 replay；未经审计不能假设两者等价。

### 6. 抢占存在双币顺序成交风险

研究回测在 challenger due open 上，先按当前币 open 平仓，再按挑战币 open 建仓。实盘只能顺序执行“reduce-only close -> venue flat confirmation -> new entry”。`Replace/AfterFlat` 可保证不重叠，但两次市场成交不会严格等于两根历史 K 的 open。必须将真实两腿滑点写入 ledger，并通过 dry-run/replay 压力确认该偏差不会破坏硬门槛。

## 建议实现顺序

1. 在 runner 新建独立 `asset_specific_six_selector`，策略身份不得复用 `BIN-1H-AR-MAE-V1`。
2. 声明六币各一组 15m 和 1h 依赖；15m 负责全局时钟、原生 15m 腿及抢占平仓参考，1h 只负责旧机制原生状态。
3. 移植 9 条 15m 腿的精确指标与 signal-strength 计算；6 条旧 1h 腿复用已经审计的参数和特征实现，但进入 V3 自己的联合状态机。
4. 实现 per-sleeve due-open 去重、cooldown、空仓仲裁、nonpreemptive 锁和 preemptive challenger 规则。
5. 先做 runner 离线 replay，逐笔对齐冻结 CSV 的 `sleeve/side/entry_ts/exit_ts/exit_reason/preemption`；不允许只对齐汇总收益。
6. 分别审计 trade-price 模拟保护与 mark-price 交易所保护，并对抢占双币成交增加额外滑点压力。
7. 通过 restart、missing-series、pending replacement、venue reconcile、全球单仓不变量测试。
8. 即使 runner parity 全部通过，仍需等未来 OOS 一次性揭示；只有未来硬门槛通过后，才讨论登记与 promotion。

## Promotion 前硬门禁

- 15 条腿和两条路线必须与机器契约逐字段一致；
- runner replay 与冻结交易账逐笔一致，汇总指标一致不足以替代逐笔核验；
- 任一必需 15m/1h 数据缺失不得增仓或抢占；
- 重启恢复后的下一次决策必须与不中断运行相同；
- venue 上任何时刻不得同时保留两个方向仓位；
- stop/TP 保护来源与研究价格源差异必须有量化审计；
- 抢占 close/open 的两次真实成本必须完整计入；
- `[2026-07-14T09:00Z, 2026-10-14T09:00Z)` 未来 OOS 完整通过冻结硬门槛。

## 当前状态

本轮只完成 runner 兼容性审计和机器执行契约，没有修改 `quant-runner` active code，也没有建立 live spec、dry-run 或 live 配置。原因不是平台不可实现，而是 V3 尚未登记且未来 OOS 未发生；提前把观察候选写成生产策略会越过研究治理边界。
