# HYPE-1D-MA7 状态边界 × V2 斜率混合诊断合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

二元/三状态迟滞候选能一致识别 MA7 regime，但把状态直接转换为仓位后暴露率超过 `92%`、short entry 的后 14 日中位顺向收益为负。登记 V2 暴露率较低，却依靠 reclaim/slope 过滤获得更高入场精度。

本合同测试：保留状态边界的持续识别与空仓能力，使用 V2 的斜率、非对称退出及风险层决定是否交易，能否兼顾“明显越界不漏单”和V2的交易质量。

不搜索参数，不改写 V2，不自动登记新版本。

## 共同状态与入场

- 下边界：`lower[t] = SMA7[t] - 0.75×ATR7[t]`
- 上边界：`upper[t] = SMA7[t] + 0.25×ATR7[t]`
- long gate：`close[t] > upper[t]` 且 `(SMA7[t]-SMA7[t-1])/ATR7[t] >= 0.02`
- short gate：`close[t] < lower[t]` 且 `(SMA7[t-2]-SMA7[t])/ATR7[t] >= 0.02`
- flat 在任意闭合日满足对应 gate 即可次开入场，不要求前一日 reclaim；
- long 跌破 lower 时次开退出；若同一闭合日 short gate 通过，可同 open 反手，否则 flat；
- short 在 `close>upper` 或 `SMA7[t]>=SMA7[t-1]` 时次开退出；只有 long gate 同时通过才反手，否则 flat；
- 多空自然信号同时成立时 long 优先（按边界定义正常不会同时成立）。

## 冻结变体

### `V2_CONTROL`

登记 V2 `1x` 原版。

### `HYBRID_CORE`

- 使用上述 persistent regime + V2 slope gate；
- `entry_mode=regime`，不使用 reclaim；
- long `entry_buffer=0.25 / exit_buffer=0.75 / slope_lookback=1 / slope_min=0.02`；
- short `entry_buffer=0.75 / exit_buffer=0.25 / slope_lookback=2 / slope_min=0.02 / slope_exit_lookback=1`；
- hard stop、trailing、max hold、cooldown 全部关闭，以隔离状态×斜率本体。

### `HYBRID_V2_RISK`

在 `HYBRID_CORE` 上零调参恢复 V2 风险层：

- long：`trail_atr=1.5`、`max_hold_days=90`、`cooldown_days=2`，无 hard stop；
- short：`hard_stop_atr=1.5`、`trail_atr=4.0`、`max_hold_days=20`、`cooldown_days=5`；
- short slope exit 保留；
- 风险/信号退出后按对应 V2 cooldown 进入 flat，再由 persistent regime gate 重入；不做 V2 特有的 trailing-stop 强制反手，以单独观察风险层。

## 数据、成本与执行

- Binance USD-M `HYPEUSDT` perpetual，accepted `1h` 聚合 UTC `1d`；
- 决策只读取闭合日 K，日 `t` 信号在 `t+1` open 成交；
- `1x`、单仓、非加仓，持仓数量固定；同 open 反手计平旧仓和开新仓两次 fill；
- 手续费 `0.001/fill`，基准不利滑点 `4 bps/fill`，压力 `8 bps/fill`；
- funding 按实际 timestamp/rate、仅在真实持仓区间结算；
- protective stop 使用真实 `1h` 路径和跳空成交规则。

## 预注册输出

- 冻结历史、prefit、后 `90d` flat-start、最新延伸；
- `4/8 bps`、额外延迟一天、零 funding；
- 最近 `1d/7d/1m/3m/6m/1y`；
- 90 日窗口、每 30 日滚动；
- `0h/12h` 与24日界相位；
- 收益、MDD、Sharpe、PF、交易数、多空归因、暴露、turnover、成本、funding、保护退出、直接反手和破产状态；
- 历史表现较好的混合变体生成自包含 HTML 交易路径；若两者均失败，仍绘制较优者供逐笔审计。

## 判定

- 先比较 `HYBRID_CORE` 与三状态候选，判断 slope gate 是否恢复入场精度；
- 再比较 `HYBRID_V2_RISK` 与 CORE，判断风险层是否改善 MDD/延迟/近期；
- 相对 V2 的比较只作诊断；现有历史已揭示，不构成 clean OOS 或 promotion。
