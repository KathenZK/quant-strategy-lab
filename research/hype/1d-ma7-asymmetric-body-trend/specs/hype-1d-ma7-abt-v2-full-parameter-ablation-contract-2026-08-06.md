# HYPE-1D-MA7-ABT-V2 全参数与斜率专项消融合同

> 冻结时间：2026-08-06（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

对已登记 [V2](hype-1d-ma7-abt-v2-spec.md) 的实际生效参数层逐项消融，并重点回答：

1. 多头自然入场的 MA7 上升斜率是否必须；
2. 空头自然入场的 MA7 下降斜率是否必须；
3. 空头持仓中的 `MA7[t] >= MA7[t-1]` 斜率退出是否必须；
4. 若全部移除斜率逻辑，V2 的收益、回撤、分期、成本、延迟与相位表现是否保持。

消融是已揭示历史上的机制解释，不修改 V2 身份，也不能直接产生 V3。

## 基准与共同口径

- 基准：登记的 V2 `1x`、UTC `0h`，含多头 trailing-stop 后真实 `1h` open 反手空；
- Binance USD-M `HYPEUSDT` perpetual，accepted `1h` 聚合 UTC `1d`，真实 event-time funding；
- 手续费 `0.001/fill`，基准不利滑点 `4 bps/fill`，压力 `8 bps/fill`；
- 冻结历史：`2025-05-31` 至 `2026-07-30 UTC`；另报告最新延伸；
- 每个变体只改声明的一个参数层，其余保持 V2。

## Active-parameter OAT 消融

### 斜率层

- `long_entry_slope_direction_only`：多头 `slope_min_atr 0.02 -> 0`，保留“必须上升”；
- `long_entry_slope_removed`：完全绕过多头入场斜率；
- `short_entry_slope_direction_only`：空头 `slope_min_atr 0.02 -> 0`，保留“必须下降”；
- `short_entry_slope_removed`：完全绕过空头自然入场斜率；
- `both_entry_slopes_removed`：同时移除多空自然入场斜率；
- `short_slope_exit_removed`：`slope_exit_lookback 1 -> 0`；
- `all_slopes_removed`：移除多空自然入场斜率及空头斜率退出。

“完全移除”使用一个不可能绑定的极低阈值，只绕过 slope gate；有限值与执行时序检查仍保留。

### 入场事件层

- `long_reclaim_removed_regime`：多头 `reclaim -> regime`；
- `short_reclaim_removed_regime`：空头 `reclaim -> regime`；
- `both_reclaims_removed_regime`：多空均改为 regime；
- `short_entry_buffer_removed`：`0.10×ATR7 -> 0`；
- `natural_long_entry_removed`：关闭自然多头，保留自然空头；
- `natural_short_entry_removed`：关闭自然空头，保留多头及其强制反手空。

### 退出、保护与 V2 状态迁移层

- `long_exit_hysteresis_buffer_removed`：多头退出 buffer `0.75 -> 0`；
- `short_exit_hysteresis_buffer_removed`：空头退出 buffer `0.25 -> 0`；
- `forced_reversal_removed`：保留 long trailing stop，但不在止损后反手，等价隔离 V2 新增状态迁移；
- `long_trailing_stop_removed`：`trail_atr 1.5 -> 0`，因此同时无 trailing 触发及其反手；
- `short_hard_stop_removed`：`hard_stop_atr 1.5 -> 0`；
- `short_trailing_stop_removed`：`trail_atr 4.0 -> 0`；
- `short_all_protective_stops_removed`：short hard/trailing 均为 0；
- `long_max_hold_removed`：`90 -> 0`；
- `short_max_hold_removed`：`20 -> 0`；
- `both_max_hold_removed`：两侧 max hold 均为 0；
- `long_cooldown_removed`：`2 -> 0`；
- `short_cooldown_removed`：`5 -> 0`；
- `both_cooldowns_removed`：两侧 cooldown 均为 0。

`confirm_days=1` 没有额外确认层；long `entry_buffer/hard_stop/slope_exit` 已为 0；`pullback_lookback`、`breakout_lookback` 在 `reclaim` 下不参与逐笔行为。这些字段列入“不活跃参数清单”，不制造伪消融。

## 斜率专项因子网格

- 多头入场 slope：`removed / direction_only(0) / 0.02 / 0.04`；
- 空头入场 slope：`removed / direction_only(0) / 0.02 / 0.04`；
- 空头 slope exit：`on / off`；
- 共 `4×4×2=32` 个预注册组合，不按结果追加点位。

## 输出与检查

- OAT 全变体：prefit、最后 `90d` flat-start、full、`8 bps`、额外延迟一天、近期 `1d/7d/1m/3m/6m/1y`、90 日滚动、`0h/12h`；
- 斜率主变体：全部 24 个日界相位分布；
- 斜率因子网格：prefit、最后 `90d`、full、压力及 `0h/12h`；
- 报告交易数、long/short 数、收益、MDD、Sharpe、PF、turnover、成本、funding、强制反手贡献和简化破产状态。

## “斜率必要”判定

分别判断多头入场、空头入场、空头退出：

- `必要`：完全移除后，full 与 `8 bps` 收益均下降，且 prefit、最后 `90d`、滚动或 24 相位中至少两项同步恶化；
- `不必要`：完全移除后 full/压力不差，MDD不恶化超过 5pp，且分期与相位没有系统性退化；
- `只需方向、不需 0.02 阈值`：阈值降到 0 优于/不差于 V2，而完全移除明显恶化；
- `证据混合`：以上条件不能形成一致结论。

`all_slopes_removed` 用于验证交互，不可替代三个部件的独立判断。
