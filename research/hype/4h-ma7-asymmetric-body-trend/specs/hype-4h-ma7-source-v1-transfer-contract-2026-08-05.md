# HYPE 4H MA7 源 V1 迁移合同

## 身份

- Family：`HYPE-4H-MA7-Asymmetric-Body-Trend`
- Alias：`HYPE-4H-MA7-ABT`
- 来源：`HYPE-1D-MA7-Asymmetric-Body-Trend-V1`
- 市场：Binance USD-M `HYPEUSDT` perpetual
- 周期：UTC 对齐 `4h`
- 状态：`explore / not promoted / not live-ready`

这是跨周期 direct-transfer 诊断，不创建本地 `V1`，也不改变源日线 V1。

## 数据与指标

- 标准数据湖 `1h` K 线聚合；每根 `4h` 必须恰有四根连续、闭合的 `1h`。
- `SMA7[t] = mean(close[t-6:t])`，对应 28 小时均线。
- `ATR7` 为 7 根 `4h` true range 的简单均值。
- 基准相位为 `00/04/08/12/16/20 UTC`，另审计整体偏移 `2h`。
- 信号仅使用已闭合 `4h`；最早于下一根 `4h` open 成交。
- intrabar stop 使用组成该 `4h` 的真实 `1h` 顺序；小时开盘跳过 stop 时按该小时 open 成交。
- funding 按真实事件时间、费率和事件小时 open，仅在真实持仓区间结算。

## 成本与仓位

- 手续费 `0.001/fill`。
- 基准不利滑点 `4 bps/fill`，压力为 `8 bps/fill`。
- 单仓、固定约 `1x`、非加仓；成交后数量保持不变。
- 多空信号同时出现时多头优先。

## 固定状态机

### 多头

- `entry_mode=reclaim`
- `slope_lookback=1`
- `slope_min_atr=0.02`
- `confirm_bars=1`
- `entry_buffer_atr=0`
- `exit_confirm_bars=1`
- `exit_buffer_atr=0.75`
- `hard_stop_atr=0`
- `trail_atr=1.5`

收盘上穿 SMA7 且 SMA7 单 bar 斜率至少为 `0.02*ATR7` 时，下一根开盘做多；收盘低于 `SMA7-0.75*ATR7` 时次开退出。trailing stop 为 `highest_close-1.5*ATR7`，收盘更新、下一 bar 生效。首持仓 bar 无固定 hard stop。

### 空头

- `entry_mode=reclaim`
- `slope_lookback=2`
- `slope_min_atr=0.02`
- `confirm_bars=1`
- `entry_buffer_atr=0.10`
- `exit_confirm_bars=1`
- `exit_buffer_atr=0.25`
- `slope_exit_lookback=1`
- `hard_stop_atr=1.5`
- `trail_atr=4.0`

收盘下穿 `SMA7-0.10*ATR7` 且两 bar SMA7 下降至少 `0.02*ATR7` 时，下一根开盘做空；收盘高于 `SMA7+0.25*ATR7` 或 SMA7 不再下降时次开退出。入场即设置 `entry+1.5*ATR7` hard stop；trailing stop 为 `lowest_close+4.0*ATR7`。

## 两种时间合同

### Bar-transfer

把源 V1 数字直接解释为 `4h` bar：

- 多头：最长 `90 bars`（15 天），冷却 `2 bars`（8 小时）。
- 空头：最长 `20 bars`（约 3.3 天），冷却 `5 bars`（20 小时）。

### Clock-equivalent

只把最长持仓和冷却乘 `6`，近似保持源日线版本的小时尺度；MA、ATR、斜率、确认和价格阈值仍按 `4h` bar：

- 多头：最长 `540 bars`（90 天），冷却 `12 bars`（2 天）。
- 空头：最长 `120 bars`（20 天），冷却 `30 bars`（5 天）。

## 冻结审计

- 全历史、`2026-05-01` 前段和最后约 `90d` flat-start；
- combined / long-only / short-only；
- `8 bps/fill`、额外延迟一根 `4h`；
- 最近 `1d/7d/1m/3m/6m/1y`；
- `0h` 与 `2h` 相位；
- 90 日滚动窗口。

证据：[诊断报告](../diagnostics/hype-4h-ma7-source-v1-transfer-2026-08-05.md) · [复现脚本](../scripts/research_hype_4h_ma7_v1_transfer.py)。
