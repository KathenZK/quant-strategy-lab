# HYPE-1D-MA7-Asymmetric-Body-Trend-V3 规格

## 身份

- Full version：`HYPE-1D-MA7-Asymmetric-Body-Trend-V3`
- Alias：`HYPE-1D-MA7-ABT-V3`
- 市场：Binance USD-M `HYPEUSDT` perpetual
- 周期：UTC `1d`；保护与反手执行使用组成日K的真实`1h`路径
- 状态：`registered / not promoted / not live-ready`
- 来源：V2空头迟滞`0.75×ATR7`诊断；由用户于2026-08-07明确登记

登记只冻结版本身份、参数、执行和成本口径，不代表promotion，也不授权runner。V3保留V2的全部机制，只扩大空头MA7迟滞退出距离；V1、V2继续保留。

## 共同口径

- `SMA7[t] = mean(close[t-6:t])`；`ATR7`为日线true range的七日简单移动平均；
- 单仓、非加仓；每次入场按成交后权益建立约`1x`目标，持仓期间数量固定；
- 手续费`0.001/fill`，基准不利滑点`4 bps/fill`，压力滑点`8 bps/fill`；
- funding按实际Binance timestamp/rate、仅在真实持仓区间结算，事件名义使用所在`1h` K open。

## 多头规则

- `entry_mode=reclaim`
- `slope_lookback=1`，`slope_min_atr=0.02`，`confirm_days=1`，`entry_buffer_atr=0`
- `exit_confirm_days=1`，`exit_buffer_atr=0.75`
- `hard_stop_atr=0`，`trail_atr=1.5`，`max_hold_days=90`，`cooldown_days=2`

日`t`收盘同时满足`close[t] > SMA7[t]`、`close[t-1] <= SMA7[t-1]`、`(SMA7[t]-SMA7[t-1])/ATR7[t] >= 0.02`时，于`t+1` open做多。

`close[t] < SMA7[t]-0.75×ATR7[t]`时次开退出；trailing stop为`highest_close-1.5×ATR7`，收盘更新、下一日生效。首持仓日无固定hard stop。

## 空头规则

- 自然入场：`entry_mode=reclaim`，`slope_lookback=2`，`slope_min_atr=0.02`，`confirm_days=1`，`entry_buffer_atr=0.10`
- 退出：`exit_confirm_days=1`，`exit_buffer_atr=0.75`，`slope_exit_lookback=1`
- 保护：`hard_stop_atr=1.5`，`trail_atr=4.0`，`max_hold_days=20`，`cooldown_days=5`

自然空头：日`t`收盘同时满足`close[t] < SMA7[t]-0.10×ATR7[t]`、`close[t-1] >= SMA7[t-1]`、`(SMA7[t-2]-SMA7[t])/ATR7[t] >= 0.02`时，于`t+1` open做空。

退出：`close[t] > SMA7[t]+0.75×ATR7[t]`或`SMA7[t] >= SMA7[t-1]`时次开退出；入场即设置`entry+1.5×ATR7` hard stop；trailing stop为`lowest_close+4.0×ATR7`，收盘更新、下一日生效。

## V2机制继承：多头trailing stop后反手

1. 当前为多头且`1.5×ATR7` trailing stop触发时，先按原保护价/跳空规则平多；
2. 若小时open已越过保护价，在该真实`1h` open反手；若小时内触发，在下一根真实`1h` open反手；
3. 反手空跳过自然short entry的reclaim、slope和buffer；
4. 平多与开空分别计手续费和不利滑点；
5. 建空后立即启用V3空头hard stop、迟滞/斜率退出、trailing、max hold和cooldown；
6. 反手当日剩余`1h`路径和funding必须计入。

多头因`ma7_hysteresis_exit`或`max_hold_days`退出时不反手。

## 成交优先级

1. 日open先执行前一完整日产生的退出；
2. 多头trailing stop按真实`1h`路径触发并执行强制反手；
3. 其他空仓时，cooldown结束后评估自然入场；多空自然信号同时成立时多头优先；
4. `1h` open跳空穿越保护价时按该open成交；小时内触发时按保护价退出；
5. stop触发后不使用未知的同小时后续路径。

## 冻结历史观察

- `2025-05-31`至`2026-07-30 UTC`：成本后`+350.85%`，MDD`-26.81%`，19笔；
- `8 bps/fill`：`+344.23%`；额外延迟一天：`+104.25%`；
- prefit`+157.31%`，后90日flat-start`+75.21%`，`12h`相位`+35.33%`；
- 相对V2的历史改善只来自prefit两笔空单各延后2日退出；主路径short hard/trailing stop均为0次。

以上是post-reveal登记观察，不是clean OOS。

## 门禁缺口

- V3尚无独立prospective OOS，不能继承V1/V2观察；
- 历史只有19笔，V3相对V2的变化只改动两笔实际退出路径；
- 强制反手不检查成交价与MA7关系：7笔中R-S02、R-S12在当时可知MA7上方开空，且7笔中5笔只持有1日；反手入场绕过slope、入场后又立即启用slope exit，构成live-readiness blocker；
- 额外延迟一天明显弱于V2；多头首持仓日无hard stop；
- 未完成CPCV、Monte Carlo、runner parity或线上对账；
- 无live spec、无quant-runner implementation、无dry-run/live授权。

## 证据

- [V2规格](hype-1d-ma7-abt-v2-spec.md)
- [空头迟滞0.75冻结合同](hype-1d-ma7-abt-v2-short-hysteresis-075-contract-2026-08-07.md)
- [空头迟滞0.75诊断](../diagnostics/hype-1d-ma7-abt-v2-short-hysteresis-075-2026-08-07.md)
- [V3全参数消融](../ablations/hype-1d-ma7-abt-v3-full-parameter-ablation-2026-08-07.md)
- [V3 3x杠杆诊断](../diagnostics/hype-1d-v3-3x-leverage-2026-08-07.md)
- [V3强制反手入场审计](../diagnostics/hype-1d-ma7-abt-v3-forced-reversal-entry-audit-2026-08-07.md)
- [V3强制反手确认修正诊断](../diagnostics/hype-1d-ma7-abt-v3-forced-reversal-confirmation-2026-08-07.md)
- [V3 1x完整交易路径HTML](../artifacts/hype_1d_ma7_abt_v3_trade_path_2026-08-07.html)
- [家族主账](../hype-1d-ma7-abt-core-ledger.md)
