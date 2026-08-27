# BIN-1D-MA7-RC Short-First 账户回测候选规格（2026-08-24）

## 身份与状态

- 名称：`BIN-1D-MA7-RC-Short-First-Candidate`。
- 来源：P1 可读市场状态与频率统计后的 outcome-derived 候选。
- 状态：`draft backtest candidate / not registered / not promoted / not live-ready`。
- 本文件只冻结下一阶段怎样做账户回测，不把事件收益冒充策略收益，也不产生 `V1`。

## 为什么先做空

P1 中，`UP_TREND` 多头 10D/20D 平均收益转正，但中位数仍为负且聚类置信区间跨零；`DOWN_TREND` 空头 20D 平均、中位数、胜率和聚类推断更一致。动态流动性 Top20 中，方向一致且高波动的空头 20D 仍保持正向，但样本已降至约 250 个有效事件，因此适合进入账户回测，不足以直接登记策略。

P1 的 compression→expansion 空头只有约 200 个全市场事件，Top20 只有约 20 个，不作为主策略，只保留 shadow 观察。

## Point-in-time 标的池

- Binance USD-M perpetual，完整 UTC 日 K。
- 每日收盘时，以截至当日的 trailing-30D `quote_volume` 中位数排序，取当日 Top20。
- 只使用当日真实存在且 P1 causal features 完整的合约；不使用今天的固定币种名单回填历史。
- 不按历史收益挑币，不按单币结果调参数。

## 市场状态

全部状态只使用信号日收盘及以前数据：

- `Normalized Slope = (SMA30[t]-SMA30[t-1])/ATR14[t]`；
- `Slope percentile`：该合约 trailing-252 当前分位；
- `ER20 percentile`：该合约 trailing-252 当前分位；
- `RV20 percentile`：该合约 trailing-252 当前分位。

`DOWN_TREND` 同时要求：

1. `Close[t] < SMA30[t]`；
2. Normalized Slope `<0`；
3. Slope percentile `<=40%`；
4. ER20 percentile `>60%`。

高波动要求 RV20 percentile `>60%`，即 Q4/Q5。

## 三条固定比较臂

### C0：方向一致对照

- 当日属于 `DOWN_TREND`；
- 当日出现 SMA7 向下突破；
- 不限制 RV 桶。

### C1：高波动主候选

- 满足 C0；
- RV20 percentile `>60%`。

### C2：压缩扩张 shadow

- 满足 C0；
- 前一日 `ATR5/ATR20` trailing-252 percentile `<=20%`；
- 突破日 `TrueRange[t]/ATR20[t-1]` trailing-252 percentile `>80%`。

C0/C1 是账户回测的正式比较；C2 只报告，不参与主候选选择。不得在运行后新增 RV 或 compression 阈值。

## 信号、买入与卖出

- Signal：`Close[t-1] >= SMA7[t-1] and Close[t] < SMA7[t]`。
- Entry：信号确认后的下一完整 UTC 日开盘，以 short 方向入场。
- 固定持有：入场后持有 20 个完整 UTC 日；在第 20 个持有日之后的下一日开盘退出。
- 不设止盈、止损、trailing stop 或反向 MA7 提前退出，以保持与事件研究的固定期限逻辑接近。
- 持仓期间同一合约的新信号忽略，不重复加仓，也不延长持有期。
- scheduled exit 缺失、合约中断或退市必须单列审计；不得静默丢弃交易。主结果与保守 adverse-exit stress 同时报告，无法核实退出价格时阻断净绩效结论。

## 账户、持仓与换仓

- Short-only，最大总 gross exposure `1.0x`，不加杠杆。
- 最多同时持有 5 个合约，每个仓位固定占初始/当日账户权益的 20% notional；空余槽位保持现金。
- 同一天候选多于空余槽位时，按当日 point-in-time `liquidity_rank` 从高到低流动性录取；并列按 symbol 字典序，保证确定性。
- 已持仓不因新信号被强制换出；只有 scheduled exit 释放槽位后才接纳新仓。
- 账户回测另做最大 3/10 槽位的预声明容量稳健性，但不得从三者中选历史最优作为登记参数。

## 成本与资金费

- Binance fee：每次成交 notional 的 `0.001`。
- adverse slippage：每次成交 `4 bps`。
- funding：使用持仓期间实际 Binance funding；若全历史资金费无法取得或无法对齐，gross 与 fee/slippage-only 可作诊断，但 final net performance 必须标记 incomplete。
- 所有成本按实际成交 notional 记入账户，不从事件平均收益中简单相减。

## 必须输出

- 每个比较臂的 gross、fee/slippage net、含实际 funding net；
- CAGR、总收益、最大回撤、Sharpe、Calmar、月度/年度收益、胜率、profit factor；
- 总交易数、独立入场日数、平均持仓数、现金比例、gross exposure、换手率、费用与 funding；
- 同日信号拥挤度、因槽位不足被拒绝的信号、收益的 symbol/year 集中度；
- 数据截止日向前 `1d/7d/1m/3m/6m/1y` 切片；
- Top20 membership、scheduled-exit 缺失、退市和终点 censor audit；
- C0 vs C1 的逐年、pre/post-2024 与 MA5/7/10 邻域对照；MA 邻域只检查结构，不选参数。

## 决策门禁

- C1 只有在成本后账户结果优于 C0、且优势不依赖单一年份/单一币/少数共同事件日时，才说明高波动过滤有增量。
- 若 C0/C1 的正事件均被槽位冲突、next-open、成本、funding 或退市审计消除，则结论为事件层 edge 不可收割，停止策略化。
- 多头不在本候选内。只有新的独立证据证明 `UP_TREND` 多头中位数、胜率和成本后账户收益同时成立，才另立多头候选。
- 本历史区间已经揭示；即使账户回测为正，也只能保持 diagnostic candidate。`2026-07-01` 之后的 point-in-time prospective 数据必须单独冻结，不能用本结果回调规则。

## 证据

- [P1 结果](../diagnostics/binance-1d-ma7-regime-continuation-p1-readable-states-frequency-2026-08-24.md)
- [P1 研究合同](binance-1d-ma7-regime-continuation-p1-readable-state-frequency-contract-2026-08-24.md)
- [P0R2 结果](../diagnostics/binance-1d-ma7-regime-continuation-p0-results-2026-08-24.md)
