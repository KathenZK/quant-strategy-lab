# HYPE V4 Short Entry Timing 诊断合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

图示2025-06-17的价格已从MA7上方跌破short entry buffer，MA7相对前一日也已拐头，但登记V4使用`2d`净斜率：跌破当日slope未通过，随后slope通过时reclaim事件已失效。本轮只隔离检验：

1. 自然short入场改用`1d`斜率会怎样；
2. 保留`2d`斜率，但让一次真实跌破保持armed、等待后续slope确认会怎样。

不搜索阈值、不修改已登记V4、不改变long、强制反手或short退出规则。

## 冻结变体

### `V4_CONTROL`

登记V4：自然short同时要求当日reclaim、`0.10×ATR7` entry buffer与`2d`向下slope；long trailing反手只在拟成交真实`1h` open低于上一完整日MA7时获准。

### `SHORT_ENTRY_SLOPE_1D`

- 只把自然short入场slope改为`(SMA7[t-1]-SMA7[t])/ATR7[t] >= 0.02`；
- short的slope exit仍严格沿用V4的`2d` lookback；
- forced trailing reversal仍只做V4的`MA_ONLY`确认，不新增slope要求。

因此该变体回答的是“入场确认从两日净下降改为单日拐头”的独立影响，不把short整套配置的`slope_lookback`机械改为1。

### `PERSISTENT_CROSS_2D`

1. 仅在flat且cooldown已结束时，若`close[t] < SMA7[t]-0.10×ATR7[t]`且`close[t-1] >= SMA7[t-1]`，登记一次fresh short cross并置为armed；
2. 若同日V4的`2d` down-slope已经达到`0.02`，照常于`t+1` open入场；
3. 若slope未通过，armed不按天数过期；
4. 后续只要日收盘仍低于SMA7，armed继续保留；当`close < SMA7-0.10×ATR7`且`2d` slope首次通过时，于下一日open开short；
5. 若等待期间`close >= SMA7`，明确穿越被否定，armed失效；必须等待下一次fresh cross；
6. 任何新仓建立后armed清零；不从被V4拒绝的intraday forced reversal直接创建armed状态。

该变体不把“始终位于MA7下方”本身当作无来源的regime入场；short仍必须能追溯到一次明确的上方到下方穿越。

## 共同执行边界

- Binance USD-M `HYPEUSDT` perpetual；accepted `1h`聚合UTC日K与真实event-time funding；
- 历史主路径截止`2026-07-30 04:00 UTC`，最新延伸使用运行时已接受数据；
- 约`1x`、固定数量、单仓、无加仓；
- 手续费`0.001/fill`、基准不利滑点`4 bps/fill`；
- 所有日线判断只使用已闭合日K，于下一日open执行；
- V4的MA_ONLY强制反手、2日cooldown、long/short保护、迟滞、max hold与退出slope均不变。

## 输出与判定

- prefit、最后90日flat-start、full；
- `8 bps`、额外延迟一天、零funding、`12h`日界；
- 最近`1d/7d/1m/3m/6m/1y`、90日滚动、24日界相位、最新延伸；
- 逐笔交易、新增/删除/改写交易归因、armed触发/确认/失效证据；
- 收益、MDD、Sharpe、PF、交易数、成本、funding与简化破产。

两种变体都属于已揭示历史上的机制诊断。即使主路径优于V4，也只能定位机制影响，不能直接登记V5或推进promotion。
