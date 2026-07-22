# BTC 30m 趋势策略首轮搜索诊断（2026-07-21）

## 结论

切换到原生 `30m` 后，完成了三条路线：

1. 将 15m 低波动压缩延续机制按相同墙钟尺度迁移到 `30m`；
2. 扩展到更高频的 Donchian/Keltner 趋势突破；
3. 放宽压缩分位数、突破窗口与 ATR 上限，检查是否能消除低频样本问题。

没有策略通过完整门禁。最有研究价值的是低频观察 `lvcb-08816b18771a`：原生 `30m`、双倍成本、最近一年和偏移 `30m` 相位均为正，但 Train 只有 `7` 笔，前三笔盈利贡献 `89.65%`，无法证明可重复性。更高频路线虽然在开发区间有大量通过项，却全部在 `2024+`、双倍成本或偏移相位审计失败。

因此本轮结论是：**30m 比 15m 出现了一个近期仍为正的低频结构，但还没有可登记或可晋升的趋势策略。**

## 数据与执行口径

- 市场：Binance USD-M Futures `BTCUSDT` perpetual
- 原生周期：`30m`
- UTC 范围：`2020-01-01 00:00` 至 `2026-07-21 07:00`，共 `114,878` 根已收盘 K 线
- 数据质量：连续性、重复键、关键空值、raw/normalized 一致性、OHLC 合法性与 funding 均通过，blocker `0`
- Train：`2020-01-01` 至 `2022-01-01`
- Validation：`2022-01-01` 至 `2024-01-01`
- Reused diagnostic：`2024-01-01` 至数据结束
- 近期审计：以数据结束时间锚定 `1d/7d/1m/3m/6m/1y`
- 成本：每次成交 fee `0.001` + adverse slippage `4 bps` + 官方 funding；双倍成本为 fee `0.002` + slippage `8 bps`
- 时序：已收盘 K 线生成信号，下一根开盘成交；入场 K 线起止损有效，gap-aware，定时退出在 K 线开盘执行
- 相位审计：将经审计原生 `15m` 聚合为 `hh:15/hh:45` 起始的偏移 `30m`；每组必须恰有两根源 K 线，不补值

本次参数选择受到既有 15m BTC 研究启发，且部分路线使用了 reused diagnostic 做研究筛选，因此没有任何历史区间被声称为 untouched OOS。fresh prospective 起点为 `2026-07-21 07:00 UTC`。

## 路线一：低频压缩延续

首轮搜索 `120` 个信号组合，再对开发排名靠前项审计退出，共 `184` 个配置。保留的观察：

- ATR 压缩分位数 `0.35`，最近 `32` 根出现压缩
- EMA `48/192` 多头趋势，slow EMA 相对 `8` 根前上升
- ATR/close `<= 0.00325`
- 收盘突破 prior Donchian `48` high
- 只做多，`5 ATR` 保护止损，最多持有 `192` 根（4 天）

| 区间 | Return | MDD | Trades | PF | 判定 |
| --- | ---: | ---: | ---: | ---: | --- |
| Train | `+32.83%` | `-5.90%` | `7` | `6.62` | 样本与集中度失败 |
| Validation | `+33.09%` | `-12.44%` | `22` | `2.69` | 单笔集中度失败 |
| Train 2x | `+30.44%` | `-6.22%` | `7` | `5.66` | 收益为正但样本不足 |
| Validation 2x | `+25.73%` | `-14.22%` | `22` | `2.15` | 收益为正 |
| Reused diagnostic | `+18.96%` | `-9.40%` | `35` | `1.56` | 仅审计 |
| Reused diagnostic 2x | `+5.36%` | `-11.11%` | `36` | `1.16` | 仅审计 |

近期原生 `30m` 切片：

| Slice | Return | Trades |
| --- | ---: | ---: |
| `1d` | `0.00%` | `0` |
| `7d` | `+1.92%` | `1` |
| `1m` | `+1.92%` | `1` |
| `3m` | `-0.26%` | `5` |
| `6m` | `+4.66%` | `6` |
| `1y` | `+17.50%` | `17` |

偏移相位仍为正：Train `+28.94%`、Validation `+39.69%`、reused diagnostic `+20.37%`、diagnostic 2x `+9.81%`，最近 `1y +17.34%`。这排除了“只依赖整点/半点 K 线边界”的直接反例，但不能修复样本不足：Train 仅 `7` 笔，且 2021 年 `0` 笔；原生全期只有 `64` 笔，年均约 `10` 笔。

其 `180d` 窗口为 `8/13` 正收益，完整自然年只有 `4/7` 为正。它适合作为低频结构观察，不足以成为版本或 promotion 候选。

## 路线二：Donchian / Keltner 高交易频率搜索

搜索覆盖：

- Donchian `12/24/48/96`
- Keltner basis `24/48`，倍数 `1.5/2.0/2.5`
- EMA `24/96`、`48/192`、`96/384`
- slope lag `4/8/16`
- 无波动限制、ATR cap `0.005`、ATR band `0.0015–0.0075`
- 可选相对成交量 `>= 1`
- `2.5/3/4/5 ATR` 止损和 `24/48/96/192` 根持有期

`324` 个信号中 `73` 个通过标准成本 development gate，`43` 个连同双倍成本通过；加入退出搜索后共 `504` 个配置、`145` 个完整 development 通过项。但对全部 `145` 个幸存项审计后，满足“reused diagnostic 正、diagnostic 2x 正、最近 1y 不低于 `-5%`”的项为 `0`。

开发排名第一项是 Donchian48 + EMA24/96 + `2.5 ATR` stop：

| 区间 | Return | MDD | Trades |
| --- | ---: | ---: | ---: |
| Train | `+75.15%` | `-12.42%` | `57` |
| Validation | `+63.26%` | `-16.59%` | `101` |
| Reused diagnostic | `-10.89%` | `-46.01%` | `206` |
| Reused diagnostic 2x | `-51.49%` | `-65.72%` | `210` |
| 最近 `1y` | `-34.02%` | `-34.83%` | `86` |

偏移相位 reused diagnostic 为 `-2.83%`，双倍成本 `-45.52%`。这不是某个小参数失灵，而是高频 breakout edge 在 `2025–2026` 明显反转；继续围绕同一通道调参会加重历史污染。

## 路线三：扩展压缩搜索

为验证路线一是否只是过滤过严，再扫描压缩分位数 `0.35/0.50/0.65/0.80`、lookback `8/16/32`、Donchian `12/24`、更宽 ATR cap `0.005–0.05` 以及多组退出。

结果 `0` 个完整 development gate 通过项。最优表面配置在 Train `+73.64%`、Validation `+25.21%`，但 validation MDD `-26.34%`，双倍成本 Validation `-11.58%`；reused diagnostic `-22.85%`，偏移相位 diagnostic `-26.47%`。放宽频率会直接把近期无效 breakout 大量引入。

## 裁决与重开条件

- 不登记任何 `Vx`，不 promotion，不创建 live spec。
- 保留 `lvcb-08816b18771a` 作为未登记低频观察，但不把历史正收益解释为已找到策略。
- 停止在现有通道、压缩、EMA、ATR cap、stop、hold 维度继续历史扩搜。
- 只有出现独立新状态机，或冻结后累计至少 `30` 笔可归因 prospective 交易，才重开。

## 证据

- [原生 30m 数据质量报告](../artifacts/btc_binance_30m_long_data_quality_latest.json)
- [低频压缩搜索摘要](../artifacts/btc_30m_tc_summary_2026-07-21.json)
- [低频压缩候选表](../artifacts/btc_30m_tc_candidates_2026-07-21.csv)
- [低频观察逐笔交易](../artifacts/btc_30m_tc_selected_trades_2026-07-21.csv)
- [低频观察滚动窗口](../artifacts/btc_30m_tc_rolling_windows_2026-07-21.csv)
- [通道趋势搜索摘要](../artifacts/btc_30m_channel_trends_summary_2026-07-21.json)
- [通道趋势候选表](../artifacts/btc_30m_channel_trends_candidates_2026-07-21.csv)
- [通道趋势选中项逐笔交易](../artifacts/btc_30m_channel_trends_selected_trades_2026-07-21.csv)
- [通道趋势滚动窗口](../artifacts/btc_30m_channel_trends_rolling_2026-07-21.csv)
- [扩展压缩搜索摘要](../artifacts/btc_30m_expanded_compression_summary_2026-07-21.json)
- [扩展压缩候选表](../artifacts/btc_30m_expanded_compression_candidates_2026-07-21.csv)
- [扩展压缩选中项逐笔交易](../artifacts/btc_30m_expanded_compression_selected_trades_2026-07-21.csv)
- [扩展压缩滚动窗口](../artifacts/btc_30m_expanded_compression_rolling_2026-07-21.csv)
- [复现脚本入口](../scripts/README.md)
