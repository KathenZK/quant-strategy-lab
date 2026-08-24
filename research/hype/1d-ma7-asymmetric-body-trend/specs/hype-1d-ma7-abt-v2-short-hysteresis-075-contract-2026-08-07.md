# HYPE-1D-MA7-ABT-V2 空头迟滞 0.75 诊断合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

登记 V2 的空头MA7迟滞退出为`close > SMA7 + 0.25×ATR7`。本诊断只把该距离改为`0.75×ATR7`，检验更宽容的空头持仓是否改善收益，以及是否开始触发原本历史零命中的short hard/trailing stop。

本次不是参数搜索，不改写V2，也不自动登记新版本。

## 冻结变体

### `V2_CONTROL`

登记V2：short `exit_buffer_atr=0.25`。

### `SHORT_EXIT_075`

只修改：

```text
short exit_buffer_atr: 0.25 -> 0.75
```

其余保持V2：

- short slope exit：`SMA7[t] >= SMA7[t-1]`；
- hard stop：`entry + 1.5×ATR7`；
- trailing：`lowest_close + 4×ATR7`；
- max hold：20日；cooldown：5日；
- long全部参数、long trailing-stop强制反手、成本和时序不变。

### 保护归因对照

仅用于识别stop来源，不作为候选：

- `SHORT_EXIT_075_NO_HARD`：在`SHORT_EXIT_075`上设short `hard_stop_atr=0`；
- `SHORT_EXIT_075_NO_TRAIL`：在`SHORT_EXIT_075`上设short `trail_atr=0`。

若`SHORT_EXIT_075`的short protective exit在`NO_TRAIL`中保持、在`NO_HARD`中消失，则归因为hard stop；反之归因为trailing。若路径交互，记录无法唯一归因，不猜测。

## 数据、成本与执行

- Binance USD-M `HYPEUSDT` perpetual，accepted `1h`聚合UTC日K；
- `1x`、单仓、非加仓，实际event-time funding；
- 手续费`0.001/fill`，基准滑点`4 bps/fill`，压力`8 bps/fill`；
- 收盘退出条件在次日open执行；保护stop使用真实`1h`路径与跳空规则；
- 冻结历史与V2一致，另报告最新延伸。

## 预注册输出

- full、prefit、后90日flat-start；
- `8 bps`、额外延迟一天、零funding、`12h`；
- 最近`1d/7d/1m/3m/6m/1y`；
- 90日滚动、24日界相位；
- 收益、MDD、Sharpe、PF、交易数、多空归因、turnover、成本、funding；
- V2和`SHORT_EXIT_075`的short hard/trailing protective exit次数及逐笔路径差异。

## 判定

- 主收益提高但MDD、延迟、近期或相位明显恶化，不采纳；
- 未改变逐笔路径则记参数历史不活跃；
- 任何结果均为已揭示历史诊断，不是clean OOS或promotion证据。
