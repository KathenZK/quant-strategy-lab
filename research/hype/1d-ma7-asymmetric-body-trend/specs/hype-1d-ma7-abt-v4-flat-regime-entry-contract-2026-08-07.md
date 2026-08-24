# HYPE V4 Flat Regime Entry 诊断合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

上一轮`PERSISTENT_CROSS_2D`把用户要求理解成“保存一次fresh cross，等待slope确认”。用户澄清后的实际规则不是事件pending，而是持续regime：

> 当前flat时，只要最新收盘仍在MA7对应一侧，且方向slope已经确认，就应在下一日open开仓；不要求前一日收盘位于MA7另一侧。long与short对称。

本轮只检验这一定义，不搜索参数、不追溯修改登记V4。

## 冻结变体

### `V4_CONTROL`

登记V4。自然long/short均使用`reclaim`，所以除了当前价格和slope，还要求前一日出现另一侧touch/cross。

### `FLAT_REGIME_ENTRY`

当且仅当`side=flat`且cooldown已经归零：

- long：`close[t] > SMA7[t]`，且沿用V4 long slope lookback/threshold；
- short：`close[t] < SMA7[t]`，且沿用V4 short的`2d` slope与`0.02`阈值；
- 满足后于`t+1` open成交；
- 不检查`close[t-1]`位于MA7哪一侧，不保留cross时间戳，也不设置事件有效期；
- 价格只要求位于MA7对应一侧，入场side buffer设为`0`；持仓后的迟滞退出buffer不变；
- 若cooldown尚未归零，即使价格和slope通过也不入场；cooldown结束后仍在对应regime则可以入场；
- long优先级、单仓约束、forced trailing reversal均沿用V4。

这一定义会在连续多日位于MA7下方时等待short slope确认，也会在连续多日位于MA7上方时等待long slope确认；它不是“必须先观察到一次cross”的状态机。

## 共同执行边界

- Binance USD-M `HYPEUSDT` perpetual；accepted `1h`聚合UTC日K与真实event-time funding；
- 历史主路径截止`2026-07-30 04:00 UTC`，最新延伸使用运行时已接受数据；
- 约`1x`、固定数量、单仓、无加仓；
- 手续费`0.001/fill`、基准不利滑点`4 bps/fill`；
- 所有日线判断只使用已闭合日K，于下一日open执行；
- V4 MA_ONLY强制反手、long/short退出、保护、迟滞、max hold与cooldown均不变。

## 输出与判定

- prefit、最后90日flat-start、full；
- `8 bps`、额外延迟一天、零funding、`12h`日界；
- 最近`1d/7d/1m/3m/6m/1y`、90日滚动、24日界相位、最新延伸；
- 逐笔交易与相对V4的交易路径变化；
- 收益、MDD、Sharpe、PF、交易数、成本、funding与简化破产。

该变体属于已揭示历史上的机制诊断。结果不能直接登记V5或推进promotion。
