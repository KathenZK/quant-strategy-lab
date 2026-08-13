# HYPE-1D-MA7-ABT-V3 全参数消融合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

对已登记[V3](hype-1d-ma7-abt-v3-spec.md)的实际生效参数层逐项消融，判断：

1. V2阶段已确认重要的多空reclaim、入场斜率、空头斜率退出与风险层，在V3的short `exit_buffer_atr=0.75`下是否仍成立；
2. V3新增的空头迟滞距离本身贡献多少，回退V2的`0.25`与完全移除迟滞各发生什么；
3. 哪些保护、max hold或cooldown参数在登记历史路径中实际未咬合；
4. 全部斜率同时移除后，V3能否退化为简单MA7穿越系统。

消融是已揭示历史上的机制解释，不修改V3身份，也不自动产生V4。

## 基准与共同口径

- 基准：登记V3 `1x`、UTC `0h`、short `exit_buffer_atr=0.75`，含多头trailing-stop后真实`1h` open反手空；
- Binance USD-M `HYPEUSDT` perpetual，accepted `1h`聚合UTC `1d`，真实event-time funding；
- 手续费`0.001/fill`，基准不利滑点`4 bps/fill`，压力`8 bps/fill`；
- 冻结历史：`2025-05-31`至`2026-07-30 UTC`；另报告最新延伸；
- 每个变体只改声明的一层，其余保持V3。

## Active-parameter OAT

### 斜率层

- `long_entry_slope_direction_only`：long `slope_min_atr 0.02 -> 0`；
- `long_entry_slope_removed`：完全绕过long入场斜率；
- `short_entry_slope_direction_only`：short `slope_min_atr 0.02 -> 0`；
- `short_entry_slope_removed`：完全绕过short自然入场斜率；
- `both_entry_slopes_removed`：同时移除多空自然入场斜率；
- `short_slope_exit_removed`：short `slope_exit_lookback 1 -> 0`；
- `all_slopes_removed`：移除多空入场斜率及short斜率退出。

“完全移除”只绕过slope gate，有限值和执行时序检查仍保留。

### 入场事件层

- `long_reclaim_removed_regime`：long `reclaim -> regime`；
- `short_reclaim_removed_regime`：short `reclaim -> regime`；
- `both_reclaims_removed_regime`：两侧均改为regime；
- `short_entry_buffer_removed`：short `0.10×ATR7 -> 0`；
- `natural_long_entry_removed`：关闭自然long；
- `natural_short_entry_removed`：关闭自然short，保留强制反手空。

### 退出、保护与状态迁移层

- `long_exit_hysteresis_buffer_removed`：long退出buffer `0.75 -> 0`；
- `short_exit_hysteresis_v2_025`：short退出buffer `0.75 -> 0.25`，显式回退V2；
- `short_exit_hysteresis_buffer_removed`：short退出buffer `0.75 -> 0`；
- `forced_reversal_removed`：关闭long trailing-stop后反手；
- `long_trailing_stop_removed`：long `trail_atr 1.5 -> 0`；
- `short_hard_stop_removed`：short `hard_stop_atr 1.5 -> 0`；
- `short_trailing_stop_removed`：short `trail_atr 4.0 -> 0`；
- `short_all_protective_stops_removed`：short hard/trailing均为0；
- `long_max_hold_removed`：`90 -> 0`；
- `short_max_hold_removed`：`20 -> 0`；
- `both_max_hold_removed`：两侧均为0；
- `long_cooldown_removed`：`2 -> 0`；
- `short_cooldown_removed`：`5 -> 0`；
- `both_cooldowns_removed`：两侧均为0。

`confirm_days=1`没有额外确认层；long `entry_buffer/hard_stop/slope_exit`已为0；`pullback_lookback`、`breakout_lookback`在`reclaim`下不参与逐笔行为。这些字段只列入不活跃参数清单。

## 斜率专项因子网格

- long入场slope：`removed / direction_only(0) / 0.02 / 0.04`；
- short入场slope：`removed / direction_only(0) / 0.02 / 0.04`；
- short slope exit：`on / off`；
- 共`4×4×2=32`个预注册组合，不按结果追加点位。

## 输出与检查

- 28个OAT变体：prefit、最后`90d` flat-start、full、`8 bps`、额外延迟一天、近期`1d/7d/1m/3m/6m/1y`、90日滚动、`0h/12h`；
- 8个关键斜率变体：24个日界相位；
- 32组斜率网格：prefit、最后`90d`、full、压力及`0h/12h`；
- 报告收益、MDD、Sharpe、PF、交易数、多空贡献、turnover、成本、funding、强制反手贡献和简化破产状态；
- 识别逐笔与V3完全相同的历史未咬合参数。

## 判定

对long入场斜率、short入场斜率和short斜率退出沿用V2消融判定：

- `必要`：完全移除后full与`8 bps`均下降，且prefit、后90日、滚动或24相位至少两项同步恶化；
- `不必要`：full/压力不差，MDD恶化不超过5pp，且分期与相位没有系统退化；
- `只需方向、不需0.02阈值`：阈值降至0不差于V3，而完全移除明显恶化；
- 其他情况为`证据混合`。

对V3的short迟滞`0.75`，只报告相对V2 `0.25`和无buffer的历史贡献；因V3本身来自已揭示历史，不使用同一历史再次“证明”其优越性。
