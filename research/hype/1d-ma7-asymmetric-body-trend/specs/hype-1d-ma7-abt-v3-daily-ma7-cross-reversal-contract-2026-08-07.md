# HYPE-1D-MA7-ABT-V3 日线跌破MA7反手诊断合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

当前V3在long `1.5×ATR7` trailing stop触发后立即反手short。用户明确指出：快速插针触发trailing可以平多，但不应自动成为做空趋势信号；真正的反手应来自完整日K由MA7上方收盘穿到MA7下方。

本诊断检验该状态迁移，不修改或重新登记V3。

## 冻结变体

### `V3_CONTROL`

登记V3：long trailing stop后按下一可用真实`1h` open反手short。

### `TRAIL_FLAT_CONTROL`

V3所有参数不变，但long trailing stop只平多到空仓，不反手。

### `DAILY_CROSS_REVERSAL`

在`TRAIL_FLAT_CONTROL`上加入：

1. 当前必须仍持有long；
2. 日`t-1`满足`close[t-1] >= SMA7[t-1]`；
3. 日`t`满足`close[t] < SMA7[t]`；
4. 在`t+1`日open先平long，再按同一open建立short；
5. 平多与开空是两次成交，分别计费和不利滑点；
6. 该反手short跳过自然short reclaim、entry buffer和入场slope；
7. 建仓后沿用V3 short `0.75×ATR7`迟滞、MA7斜率退出、hard/trailing、max hold和cooldown；
8. 若long已在日内被trailing stop平仓，则日末不再反手；trailing stop始终只回到空仓。

不增加额外`min_hold_days`。由于反手条件只在实际持有long时检查，至少已经经历入场后的一个完整收盘判定；本轮不事后搜索“持有多久才算正常”。

## 数据、成本与执行

- Binance USD-M `HYPEUSDT` perpetual，accepted `1h`聚合UTC日K；
- 约`1x`、单仓、非加仓，真实event-time funding；
- 手续费`0.001/fill`，基准滑点`4 bps/fill`，压力`8 bps/fill`；
- 日线cross只读取完整收盘，在下一日open执行，不使用日内未来信息；
- 其余V3参数、优先级和冻结历史不变。

## 输出

- prefit、最后`90d` flat-start、full；
- `8 bps`、额外延迟一天、零funding、`12h`；
- 最近`1d/7d/1m/3m/6m/1y`、90日滚动、24日界相位、最新延伸；
- 收益、MDD、Sharpe、PF、交易数、多空贡献、成本、funding和简化破产；
- trailing反手与日线cross反手的次数、逐笔收益、退出原因和交易路径。

## 判定

- 必须先确认`R-S02`类trailing反手已消失，且所有新增反手均有严格的“前收在MA7上、当收在MA7下”证据；
- 收益提高但依赖一笔已揭示交易、延迟/相位/回撤恶化时，不写回V3；
- 结果是post-reveal机制诊断，不是clean OOS或promotion证据。
