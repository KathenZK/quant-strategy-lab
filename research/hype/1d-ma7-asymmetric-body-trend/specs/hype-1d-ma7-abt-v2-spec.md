# HYPE-1D-MA7-Asymmetric-Body-Trend-V2 规格

## 身份

- Full version：`HYPE-1D-MA7-Asymmetric-Body-Trend-V2`
- Alias：`HYPE-1D-MA7-ABT-V2`
- 市场：Binance USD-M `HYPEUSDT` perpetual
- 周期：UTC `1d`，保护与反手执行使用组成日 K 的真实 `1h` 路径
- 状态：`registered / not promoted / not live-ready`
- 来源：V1 多头 trailing stop 后反手空诊断；由用户于 2026-08-06 明确登记。

登记只冻结版本身份、参数、执行和成本口径，不代表 promotion，也不授权 runner。V2 是 materially new main version，V1 保留。

## 共同口径

- `SMA7[t] = mean(close[t-6:t])`；`ATR7` 为日线 true range 的七日简单移动平均。
- 单仓、非加仓；每次入场按成交后权益建立约 `1x` 目标，持仓期间数量固定。
- 手续费 `0.001/fill`，基准不利滑点 `4 bps/fill`，压力滑点 `8 bps/fill`。
- funding 按实际 Binance timestamp/rate、仅在真实持仓区间结算，事件名义使用所在 `1h` K open。

## 多头规则

- `entry_mode=reclaim`
- `slope_lookback=1`，`slope_min_atr=0.02`，`confirm_days=1`，`entry_buffer_atr=0`
- `exit_confirm_days=1`，`exit_buffer_atr=0.75`
- `hard_stop_atr=0`，`trail_atr=1.5`，`max_hold_days=90`，`cooldown_days=2`

日 `t` 收盘同时满足 `close[t] > SMA7[t]`、`close[t-1] <= SMA7[t-1]`、`(SMA7[t]-SMA7[t-1])/ATR7[t] >= 0.02` 时，于 `t+1` open 做多。

`close[t] < SMA7[t] - 0.75×ATR7[t]` 时次开退出；trailing stop 为 `highest_close - 1.5×ATR7`，收盘更新、下一日生效。首持仓日无固定 hard stop。

## 空头规则

- 自然入场参数：`entry_mode=reclaim`，`slope_lookback=2`，`slope_min_atr=0.02`，`confirm_days=1`，`entry_buffer_atr=0.10`
- 退出参数：`exit_confirm_days=1`，`exit_buffer_atr=0.25`，`slope_exit_lookback=1`
- 保护参数：`hard_stop_atr=1.5`，`trail_atr=4.0`，`max_hold_days=20`，`cooldown_days=5`

自然空头：日 `t` 收盘同时满足 `close[t] < SMA7[t]-0.10×ATR7[t]`、`close[t-1] >= SMA7[t-1]`、`(SMA7[t-2]-SMA7[t])/ATR7[t] >= 0.02` 时，于 `t+1` open 做空。

退出：`close[t] > SMA7[t]+0.25×ATR7[t]` 或 `SMA7[t] >= SMA7[t-1]` 时次开退出；入场即设置 `entry+1.5×ATR7` hard stop；trailing stop 为 `lowest_close+4.0×ATR7`，收盘更新、下一日生效。

## V2 身份级变化：多头 trailing stop 后反手

1. 当前为多头且 `1.5×ATR7` trailing stop 触发时，先按原保护价/跳空规则平多；
2. 若小时 open 已越过保护价，在该真实 `1h` open 反手；若小时内触发，在下一根真实 `1h` open 反手，避免猜测同小时路径先后；
3. 反手空跳过自然 short entry 的 reclaim / slope / buffer；
4. 平多与开空是两次成交，分别计手续费和不利滑点；
5. 反手空建立后立即启用上述 V2 空头 hard stop，并完整沿用空头退出、trailing、最长持仓与 cooldown；
6. 反手当日剩余 `1h` 路径和 funding 必须计入；若日末最后一小时触发，待下一 UTC 日 open 才建空。

多头因 `ma7_hysteresis_exit` 或 `max_hold_days` 退出时不反手。

## 成交优先级

1. 日 open 先执行已有仓位由前一完整日产生的退出；
2. 多头 trailing stop 触发时按上节执行 V2 强制反手；
3. 其他空仓时，cooldown 结束后评估自然入场；多空自然信号同时成立时多头优先；
4. `1h` open 跳空穿越保护价时按该 open 成交；小时内触发时按保护价退出，并从下一根 `1h` open 起计算反手仓风险；
5. stop 触发后不使用未知的同小时后续路径。

## 冻结历史观察

- `2025-05-31` 至 `2026-07-30 UTC`：成本后 `+322.59%`，MDD `-26.81%`，19 笔；
- `8 bps/fill`：`+316.37%`；额外延迟一天：`+135.36%`；
- 新增反手空 7 笔、3 胜 4 负；其增量收益高度集中在 2026-07-11 后一笔；
- prefit 低于 V1 `2.51pp`，`12h` 相位为 `+14.50%`、低于同相位 V1 `14.46pp`。

这些结果是 post-reveal 登记观察，不是 clean OOS。

## 门禁缺口

- V2 尚无独立 prospective OOS；V1 的前瞻台账不能追溯转记为 V2；
- 历史只有 19 笔、强制反手只有 7 笔，增量收益集中；
- 多头首持仓日无 hard stop，未完成 CPCV、Monte Carlo、stress/phase 扩展、runner parity 或线上对账；
- 无 live spec、无 quant-runner implementation、无 dry-run/live 授权。

## 证据

- [首次运行前冻结合同](hype-1d-ma7-abt-trailing-stop-short-reversal-contract-2026-08-06.md)
- [V2 形成诊断](../diagnostics/hype-1d-v1-trailing-stop-short-reversal-2026-08-06.md)
- [全参数与斜率专项消融](../ablations/hype-1d-ma7-abt-v2-full-parameter-ablation-2026-08-06.md)
- [家族主账](../hype-1d-ma7-abt-core-ledger.md)
