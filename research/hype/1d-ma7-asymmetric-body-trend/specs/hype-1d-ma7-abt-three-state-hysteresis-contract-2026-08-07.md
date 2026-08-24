# HYPE-1D-MA7-ABT 二元/三状态迟滞诊断合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

用户原始机制是：日 K 真正站上 MA7 后持多，轻微跌破仍容忍；跌破下容错边界后平多并反手空；空头同理。该机制若只允许多/空，会在长期围绕 MA7 震荡时始终暴露方向风险。

本合同回答：

1. 不再要求 reclaim/slope、直接按 MA7±ATR 边界翻仓，能否解决“已经跌破仍不开空、已经站上仍不开多”；
2. 在二元迟滞上增加“连续位于震荡区后空仓”，能否降低震荡期损失；
3. 新机制相对登记 V2 的收益、回撤、交易成本、延迟和相位稳健性如何。

该诊断不改写 V2，也不自动登记 V3。

## 冻结变体

### `V2_CONTROL`

登记的 V2 `1x` 原版：`reclaim + slope + hysteresis/protection + long trailing-stop 后反手空`。

### `BINARY_D075`

- `upper[t] = SMA7[t] + 0.75×ATR7[t]`
- `lower[t] = SMA7[t] - 0.75×ATR7[t]`
- flat：`close>=upper -> long`；`close<=lower -> short`；否则继续 flat；
- long：`close<=lower -> short`，否则继续 long；
- short：`close>=upper -> long`，否则继续 short；
- 多空转换在次日 open 先平旧仓再开新仓，计两次 fill；
- 无 slope、reclaim、cooldown、max hold、hard/trailing stop。

### `TRI_D075_N025_K3`

在 `BINARY_D075` 上增加：

- `neutral_upper[t] = SMA7[t] + 0.25×ATR7[t]`
- `neutral_lower[t] = SMA7[t] - 0.25×ATR7[t]`
- 若完整日线收盘连续 `3` 天位于 neutral band，记为震荡确认；
- long/short 先检查反方向 `0.75×ATR7` 外边界；若越界则直接反手；
- 未越过反向外边界但震荡确认时，次日 open 平仓转 flat；
- flat 只有重新突破 `±0.75×ATR7` 外边界才入场；
- 离开 neutral band 后连续计数归零。

优先级固定为：`反方向外边界直接反手 > 震荡确认转 flat > 保持当前状态`。

## 共同执行与成本

- Binance USD-M `HYPEUSDT` perpetual，accepted `1h` 聚合完整日 K；
- `SMA7` 与 `ATR7` 均只使用闭合日 K；
- 日 `t` 收盘信号最早在 `t+1` open 成交；额外延迟场景在 `t+2` open 成交；
- `1x` 目标、单仓、非加仓，持仓期间数量固定，翻仓按平仓后权益重新建立 `1x`；
- 手续费 `0.001/fill`，基准不利滑点 `4 bps/fill`，压力 `8 bps/fill`；
- funding 按实际事件 timestamp/rate、仅在真实持仓区间结算；
- 无保护止损的变体必须用真实 `1h` high/low 审计 intraday bankruptcy；若权益触及 0，立即归零；
- 终点强制平仓。

## 预注册输出

- 冻结历史、prefit、最后 `90d` flat-start、最新延伸；
- `4/8 bps`、额外延迟一天、零 funding；
- 最近 `1d/7d/1m/3m/6m/1y`；
- 90 日窗口、每 30 日滚动；
- `0h/12h` 及 24 个日界相位；缺 terminal open 的相位记 unavailable；
- 收益、MDD、Sharpe、PF、交易数、多空数、flip/neutral-exit 数、暴露率、turnover、成本、funding、最大实际杠杆和破产状态；
- `TRI_D075_N025_K3` 自包含 HTML 交易路径。

## 判定

- 首要检查：三状态能否在不归零/不破产的前提下，相对二元状态降低 MDD、成本或负滚动窗口；
- 若三状态主收益更高但依赖单一时期，或压力/延迟/相位大面积翻负，只记机制观察；
- 无论相对 V2 是否更优，现有历史均已揭示，不构成 clean OOS 或 promotion 证据。
