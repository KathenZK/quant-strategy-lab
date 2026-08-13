# HYPE V4 Cooldown 消融合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

登记V4继承long `cooldown_days=2`与short `cooldown_days=5`。V3历史消融显示long cooldown逐笔零影响、short cooldown有明显防反复作用；本轮只在登记V4上确认三种删除方式，不搜索新天数。

## 冻结变体

- `V4_CONTROL`：登记V4，long cooldown 2日、short cooldown 5日；
- `NO_LONG_COOLDOWN`：仅long `cooldown_days=0`；
- `NO_SHORT_COOLDOWN`：仅short `cooldown_days=0`；
- `NO_BOTH_COOLDOWN`：long与short均为0。

其余long/short参数、V4 MA_ONLY强制反手确认、自然reclaim、slope、entry/exit buffer、保护、成本和执行时序全部不变。

## Cooldown边界

- 普通long退出后使用long cooldown；
- V4强制反手被MA7确认拒绝后使用long cooldown；
- 普通short退出后使用short cooldown；
- 成功的long trailing-to-short反手不等待cooldown；
- cooldown只禁止新自然入场，不延长现有仓位，也不改变已发出的退出。

## 数据与输出

- Binance USD-M `HYPEUSDT` perpetual；accepted `1h`聚合UTC日K与真实event-time funding；
- 历史主路径截止`2026-07-30 04:00 UTC`，约`1x`、单仓、固定数量；
- 每fill手续费`0.001`、基准不利滑点`4 bps`；
- 输出prefit、最后90日flat-start、full、`8 bps`、额外延迟一天、零funding、`12h`、最近切片、90日滚动、24相位与最新延伸；
- 对比交易数、重复入场、逐笔路径、收益、MDD、Sharpe与PF。

本轮是post-reveal OAT消融。零影响只代表历史未咬合；有改善也不能直接改写V4或登记新版本。
