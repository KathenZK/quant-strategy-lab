# HYPE 1D MA7 原始意图优化：Development 消融（2026-08-09）

## 角色与范围

本文只解释预注册 Development 搜索中各模块和参数对交易路径的影响。它使用 researcher-exposed `D=[0,259)`，不是 OOS 报告，也不提供 promotion 或版本登记许可。

完整运行共 `174` 行、`169` 个唯一配置，全部 `OK`；最终没有配置通过 Development 双重支配门，因此没有 champion，V/H 未揭示。机器真值以[完整 trials](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_development_trials.json)为准，整体裁决见[Development 诊断](../diagnostics/hype-1d-ma7-intent-optimization-development-2026-08-09.md)。

## Structure OAT：先证明模块接线

Structure OAT 使用固定 anchor，只回答“关闭模块是否实际改变状态与交易路径”，不参与 174 行排名。共同 gate-MDD 使用 V4-compatible daily-extreme 口径。

| ID | 结构 | D 收益 | MDD | 交易 | 相对 anchor 的解释 |
| --- | --- | ---: | ---: | ---: | --- |
| `OAT00` | 完整原始意图 | `-26.398898%` | `-56.979247%` | 26 | anchor |
| `OAT01` | persistent regime 负控制 | `-19.061969%` | `-52.732103%` | 37 | 路径改变；取消 freshness 仍失败 |
| `OAT02` | 关闭 armed | `+3.523398%` | `-46.868498%` | 23 | 收益 `+29.922297pp`，MDD改善 `10.110749pp` |
| `OAT03` | 关闭 entry slope | `-22.340189%` | `-57.036353%` | 37 | 多交易但无实质改善，entry slope 有过滤作用 |
| `OAT04` | 关闭 slope-loss exit | `+24.394881%` | `-42.787159%` | 15 | 收益 `+50.793779pp`，MDD改善 `14.192088pp` |
| `OAT05` | 关闭 adverse band | `+1.993167%` | `-46.067771%` | 34 | 收益 `+28.392066pp`，MDD改善 `10.911477pp` |
| `OAT06` | 关闭 RSI TP | `-37.093468%` | `-60.150098%` | 24 | 收益恶化 `10.694570pp`，MDD恶化 `3.170851pp` |
| `OAT07` | 关闭 overbought memory | `-26.398898%` | `-56.979247%` | 26 | 完全 path-equal，`historically_dormant` |
| `OAT08` | 关闭 direct reversal | `-8.105911%` | `-40.954666%` | 23 | 收益 `+18.292987pp`，MDD改善 `16.024581pp` |

OAT gate 为 `PASS`：除已明确标记 dormant 的 overbought 外，所有核心结构消融都改变了 trade path 和 activation count，trace parity 全部通过。这里最强的因果信号不是某个参数值，而是 slope-loss、armed、adverse band 和 direct reversal 在 anchor 上均产生负贡献；RSI TP 则产生正贡献。

## Stage A：fresh、armed 与 slope

Stage A 为全因子 `N∈{1,2,3} × A∈{0,1,2} × L∈{1,2,3} × theta∈{0,0.01,0.02,0.04}`，共 108 行。排名前五为 `A004, A016, A050, A038, A040`。

### 参数规律

- `N=2` 的整体分布比 `N=1/3` 稳，但收益较高的尾部集中在 `N=1,L=1,theta=0.04`，说明交互很强，没有平滑平台。
- `A=2` 明显弱；`A=0/1` 接近。高排名配置分别利用 A0 的 WFO 收益和 A1 的 D-full 收益，不能解释为“等待一天普遍有效”。
- `L=1` 的平均 WFO 收益约 `18.109%`，高于 `L=2/3` 的 `0.904%/-0.365%`；更长 lookback 没有带来普遍稳定性。
- `theta=0.04×ATR7` 是最有效的入场方向过滤；`theta=0` 平均 D 收益约 `-20.497%`、MDD约 `-46.825%`，说明完全不要求斜率会放大噪声。
- 最佳 MDD 配置落在更长前置侧别/更少交易区域，但其收益远不足以匹配 V4。

Stage A 的关键矛盾是：加强 freshness/slope 过滤能减少噪声，却没有恢复 V4 的大趋势持有路径；放宽又会迅速增加震荡交易。

## Stage B：ATR band 与 slope-loss 确认

Stage B 只在 Stage A 的 5 个父节点上搜索 `H∈{0.5,0.75,1.0}` 与 `C∈{1,2}`，共 30 行。

| 分支 | D 收益 / MDD | WFO 收益 / MDD | 解释 |
| --- | ---: | ---: | --- |
| `B001`：A004 + `H=.5,C=1` | `+30.187515% / -34.107914%` | `+43.097179% / -23.973966%` | Stage C 的首个父节点 |
| `B003`：A004 + `H=.75,C=1` | 与 B001 完全相同 | 与 B001 完全相同 | `.5/.75` 在该路径上等价 |
| `B005`：A004 + `H=1,C=1` | 低于 B001/B003 | 低于 B001/B003 | 更宽 band 未改善趋势持有 |
| `B025/B027/B029`：A040 + 三个 H、`C=1` | 约 `+34.5891% / -20.8076%` | 约 `+34.2839% / -16.2299%` | 风险较低，但收益远落后 V4 |

主要结论：

- `C=1` 在入围父节点的数值分布优于 `C=2`；简单延长至 2 日不是可靠修复。
- `H=.5` 与 `.75` 经常 path-equal；`H=1.0` 通常更差。
- 但 structure OAT 中完全关闭 slope-loss 比 `C=1/2` 都好，说明 `{1,2}` 网格没有覆盖真正可疑的结构边界。不能在本轮结束后补搜“关闭”并把结果当作原搜索 champion；这应是新合同的问题。

## Stage C：short RSI6 盈利止盈

Stage C 在 `B001/B003/B007` 三个父节点上搜索 `T∈{25,30,35}`、`M∈{2,3,4}`，共 27 行。

| Trial | RSI TP | D 收益 | D MDD | WFO 收益 | WFO MDD |
| --- | --- | ---: | ---: | ---: | ---: |
| `B001` | 关闭 | `+30.187515%` | `-34.107914%` | `+43.097179%` | `-23.973966%` |
| `C001` | `<25` × 2 日 | `+62.122192%` | `-29.245335%` | `+63.152465%` | `-23.973966%` |
| `C005` | `<30` × 3 日 | `+53.507872%` | `-29.245335%` | `+54.483402%` | `-23.973966%` |
| `C008` | `<35` × 3 日 | `+51.197014%` | `-26.877555%` | `+52.157859%` | `-21.429782%` |
| `C019` | A1 父节点 + `<25` × 2 日 | `+63.654201%` | `-29.245335%` | `+62.009456%` | `-23.973966%` |

`B001→C001` 同时改善收益、MDD、short PnL 和利润回吐：

- D 收益 `+31.934677pp`；MDD改善 `4.862579pp`；
- WFO 收益 `+20.055286pp`；
- short net PnL `-0.053652 → +0.185354`；
- short mean/median giveback `9.135014%/9.095525% → 6.240072%/5.623540%`；
- C001 的 3 笔 RSI TP 全胜，合计净 PnL `+0.619673`。

RSI TP 因而是明确的正向模块，但最优的 `25/2` 来自已揭示 D 搜索，不能直接升级为 production 参数。不同阈值在收益和 MDD间仍有取舍，且没有任何组合支配 V4。

## Stage D：overbought memory

Stage D 将前三个 C parent 分别加入 `M_ob∈{2,3,4}`，共 9 行。`D001–D009` 的 actions、path 与去除 trial-specific ID 后的逐笔经济签名均与各自 C parent 相同；raw trades SHA 会因 trial ID 不同而不同：

- 没有一次“此前连续 `RSI6>70` 后的 fresh down-cross”在原 slope 条件未通过时独立放行 short；
- 调整连续天数没有产生行为变化；
- Structure OAT 关闭 overbought 也与完整 anchor path-equal。

所以当前历史只能得出“模块 dormant / 样本不可识别”，不能得出阈值应该是 2、3 或 4 日，也不能声称该逻辑有效或无效。继续微调天数没有研究价值。

## Final pool 与接受门

最终池 15 行只有 4 组基础绩效簇；`C001` 依冻结顺序第一个接受门检验。它在 D-full 收益和 MDD、WFO MDD、`8 bps` full/WFO 压力上全部失败。所有 174 行的 `dominance_domains` 均为 0，因此不存在被排序遗漏的双重支配候选。

| 统计 | 数量 |
| --- | ---: |
| D-full 收益超过 V4 | `0/174` |
| D-full MDD优于 V4 | `13/174` |
| WFO 收益超过 V4 | `8/174` |
| WFO MDD优于 V4 | `60/174` |
| WFO 收益与 MDD同时优于 V4 | `0/174` |
| 至少一个 `8 bps` double-worse | `161/174` |
| WFO 零交易配置 | `10/174` |

零交易配置的 `0%` return / `0%` MDD 不是风险优势。13 个同时改善 D-full 和 WFO MDD的配置中，较高收益簇约为 `A040/B025/B027/B029`：D `+34.5891%/-20.8076%`、WFO `+34.2839%/-16.2299%`，但只产生 8/4 笔并牺牲大部分 V4 收益。

## 可以保留的机制结论

1. Fresh event 与 entry slope 都会改变路径；完全取消 entry slope 增加交易却不改善结果，因此它仍是必要的噪声过滤器。
2. Short RSI6 盈利止盈明确减少利润回吐，是最值得在新合同中独立复验的模块。
3. 当前单日 slope-loss 是最大 churn 来源；问题应从持仓状态定义重构，而非继续在 `C=1/2` 内微调。
4. Direct reversal 和 armed-band 组合会把错误退出转成错误反向仓位，值得拆成“先平仓”和“新事件再入场”两个状态。
5. Overbought memory 完全 dormant，不具备参数识别条件。
6. 更低回撤可通过减少交易获得，但现有机制无法同时保留 V4 的收益捕获。

## 不可事后救援边界

- 不因 OAT 的“关闭 slope-loss”表现较好而在本轮追加 trial；OAT 不是数值 champion pool。
- 不把 `C019` 的最高 D-full 收益、`A060` 的最佳 MDD或任何零交易 WFO 行替补为 champion。
- 不用 V/H 判断下一组参数；两段仍未揭示。
- 不登记 C001、`T=25/M=2`、`theta=.04` 或任何 D 参数为 V5。
- 后继若重构 slope-loss、direct reversal 或 band，必须视为 materially new mechanism，另写合同并重新锁定边界。

## 证据

- [预注册合同](../specs/hype-1d-ma7-intent-optimization-preregistration-2026-08-09.md)
- [Development 诊断](../diagnostics/hype-1d-ma7-intent-optimization-development-2026-08-09.md)
- [174-row trials](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_development_trials.json) · [SHA256](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_development_trials.sha256)
- [Development 裁决](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_development.json) · [SHA256](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_development.sha256)
- [D-only C001/V4 交易路径](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_failed_first_c001_development_trade_path.html) · [SHA256](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_failed_first_c001_development_trade_path.sha256)
