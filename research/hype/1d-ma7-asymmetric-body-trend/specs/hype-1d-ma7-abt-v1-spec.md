# HYPE-1D-MA7-Asymmetric-Body-Trend-V1 规格

## 身份

- Full version：`HYPE-1D-MA7-Asymmetric-Body-Trend-V1`
- Alias：`HYPE-1D-MA7-ABT-V1`
- 市场：Binance USD-M `HYPEUSDT` perpetual
- 周期：UTC `1d`
- 状态：`registered / not promoted / not live-ready`
- 来源：2026-08-04 separated-trend search 的第 `041` 组 post-reveal observation。

登记只冻结下列参数、状态机、数据与成本口径，不代表完成 promotion review，也不授权 runner。

## 共同口径

- `SMA7[t] = mean(close[t-6:t])`。
- `ATR7` 为日线 true range 的七日简单移动平均。
- 单仓、非加仓；入场按成交后权益建立约 `1x` 目标，持仓期间数量不变。
- 手续费 `0.001/fill`，基准不利滑点 `4 bps/fill`，压力滑点 `8 bps/fill`。
- funding 按实际 Binance timestamp/rate、仅在真实持仓区间结算，事件名义使用所在 `1h` K 的 open。

## 多头参数与规则

- `entry_mode=reclaim`
- `slope_lookback=1`
- `slope_min_atr=0.02`
- `confirm_days=1`
- `entry_buffer_atr=0`
- `exit_confirm_days=1`
- `exit_buffer_atr=0.75`
- `hard_stop_atr=0`
- `trail_atr=1.5`
- `max_hold_days=90`
- `cooldown_days=2`

日 `t` 收盘同时满足 `close[t] > SMA7[t]`、`close[t-1] <= SMA7[t-1]`、`(SMA7[t]-SMA7[t-1])/ATR7[t] >= 0.02` 时，于 `t+1` open 做多。

`close[t] < SMA7[t] - 0.75*ATR7[t]` 时次开退出；trailing stop 为 `highest_close - 1.5*ATR7`，收盘更新、下一日生效。首持仓日无固定 hard stop，是 live-readiness blocker。

## 空头参数与规则

- `entry_mode=reclaim`
- `slope_lookback=2`
- `slope_min_atr=0.02`
- `confirm_days=1`
- `entry_buffer_atr=0.10`
- `exit_confirm_days=1`
- `exit_buffer_atr=0.25`
- `slope_exit_lookback=1`
- `hard_stop_atr=1.5`
- `trail_atr=4.0`
- `max_hold_days=20`
- `cooldown_days=5`

日 `t` 收盘同时满足 `close[t] < SMA7[t]-0.10*ATR7[t]`、`close[t-1] >= SMA7[t-1]`、`(SMA7[t-2]-SMA7[t])/ATR7[t] >= 0.02` 时，于 `t+1` open 做空。

`close[t] > SMA7[t]+0.25*ATR7[t]` 或 `SMA7[t] >= SMA7[t-1]` 时次开退出；入场即设置 `entry+1.5*ATR7` hard stop；trailing stop 为 `lowest_close+4.0*ATR7`，收盘更新、下一日生效。

## 成交优先级

1. 日 open 先执行前一完整日产生的退出。
2. 空仓且冷却结束时再执行入场；多空信号同时成立时多头优先。
3. `1h` open 跳空穿越保护价时按该小时 open 成交；小时内触发时按保护价成交，再计不利滑点和手续费。
4. stop 触发后不使用该小时之后的价格极值计算持仓路径。

## 冻结证据与门禁缺口

- [候选观察规格](hype-1d-ma7-abt-separated-trend-observation-2026-08-04.md)
- [搜索与验证报告](../diagnostics/hype-1d-ma7-abt-separated-trend-search-2026-08-04.md)
- [BTC/ETH 零调参迁移诊断](../../../asset-portfolios/1d-ma7-separated-trend-transfer/diagnostics/binance-1d-ma7-separated-trend-transfer-2026-08-05.md)
- [BTC 周 K 零调参迁移诊断](../../../btc/1w-ma7-asymmetric-body-trend/diagnostics/btc-1w-ma7-v1-transfer-2026-08-05.md)
- [SOX 全历史零调参迁移诊断](../../../sox/1d-ma7-separated-trend-transfer/diagnostics/sox-1d-ma7-v1-transfer-2026-08-05.md)
- [家族主账](../hype-1d-ma7-abt-core-ledger.md)

缺口：历史选择为 post-reveal、仅 13 笔、HYPE 与 BTC/ETH 的相位门禁失败、BTC/ETH 日线组合与 BTC 周线直迁失败、SOX 全历史绝对与超额收益失败、多头首日无 hard stop、无 clean prospective OOS / CPCV、runner parity 或线上对账。
