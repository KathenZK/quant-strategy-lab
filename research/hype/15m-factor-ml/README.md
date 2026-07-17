# HYPE-15M-Factor-ML

完整家族名：`HYPE-15M-Factor-ML`；历史别名：`HYPE-15M-FML`。

本家族只研究 Binance HYPEUSDT 永续 `15m` 的数据湖因子与 LightGBM 交易策略，不继承或改写 HYPE-EMA、MII、Micro-Scalp、Pullback-Trail 等既有家族的身份、参数或结论。

当前状态：`explore / not promoted / not live-ready`。

目标是维护一个按信息增量扩展、而不是按固定数量凑数的候选因子库，预测扣除成本后的可交易结果，并以净收益、胜率、利润因子、最大回撤、交易覆盖和执行可行性共同审计。Round 2 候选库为 `157` 个连续因子，模型只从中选取低冗余子集；因子数量以后可以增加或减少，但新增因子必须通过公式、方向、warmup、覆盖率、因果前缀和相关性审计。

Round 2 OOS 硬筛选线为：交易数 `>=30`、胜率 `>=55%`、利润因子 `>=1.30`、最大回撤 `<=20%`、净收益为正，并与同期买入持有比较。一次性锁定 OOS 为 `2026-04-17 00:00 UTC` 至 `2026-07-16 15:30 UTC`；冻结的四种子 LightGBM 集成在该窗口产生 `0` 笔交易，同期买入持有净收益约 `+48.64%`，因此结论为 `HARD-GATE-FAILED / not promoted / not live-ready`。不得使用这段 OOS 反向降低阈值或继续调参。

入口：

- [核心台账](hype-15m-factor-ml-core-ledger.md)
- [决策日志](decision-log.md)
- [Round 2 诊断](diagnostics/hype-15m-factor-ml-round2-2026-07-16.md)
- [研究脚本](scripts/)
- [研究产物](artifacts/)
