# BTC-15M-TC 空头专属参数搜索（2026-07-21）

## 结论

围绕 `BTC-15M-Trend-Continuation` 的“低波动压缩 + EMA 趋势 + Donchian 突破”机制，单独对空头方向完成一轮参数搜索。`576` 个信号配置中，development gate 通过项为 `0`；加入 `12` 个近失父项的退出参数后，共评估 `804` 个配置，完整门禁通过项仍为 `0`。

因此没有产生空头 research candidate，不登记版本，也不把空头并入现有 long-only 候选 `lvcb-913f4ff89386`。当前家族仍保持只做多的冻结观察。

## 协议

- 市场：Binance USD-M Futures `BTCUSDT` perpetual
- 周期：原生 `15m`
- 数据：`2020-01-01 00:00 UTC` 至 `2026-07-21 07:15 UTC`，`229,757` 根；DQ blocker `0`
- Train：`2020-01-01` 至 `2022-01-01`
- Validation：`2022-01-01` 至 `2024-01-01`
- Reused diagnostic：`2024-01-01` 至数据结束，仅在开发排序后揭示
- 成本：fee `0.001/fill` + adverse slippage `4 bps/fill` + 官方 funding
- 执行：收盘确认空头信号，下一根开盘入场；入场 K 线起止损有效，gap-aware；单仓 `1.0x`

参数只按 Train/Validation 及开发双倍成本门禁排序。由于空头机制来自已使用全历史设计的 LVCB 家族，本次仍不声称存在 untouched historical OOS。

## 搜索空间

- 压缩分位：`0.20/0.30/0.40/0.50`
- 压缩回看：`8/16/32` 根
- Donchian breakdown：`48/96/192` 根
- EMA：`48/192`、`96/384`
- 慢线斜率 lag：`8/16`
- `ATR96/close` 上限：`0.0030/0.0035/0.0040/0.0050`
- 初始止损：`2/3/4/5/6 ATR`
- 最长持有：`48/96/192/384` 根

信号要求快 EMA 低于慢 EMA、慢 EMA 继续下降，并且收盘跌破 prior Donchian low。它不是把多头交易结果简单取反，而是重新搜索空头专属趋势、波动和退出参数。

## 门禁结果

| 阶段 | 数量 |
| --- | ---: |
| 信号配置 | `576` |
| 信号 development gate 通过 | `0` |
| 信号完整双倍成本门禁通过 | `0` |
| 退出搜索父项 | `12` |
| 总配置 | `804` |
| 最终完整门禁通过 | `0` |

没有任何信号同时满足 Train/Validation 正收益、样本数、PF、MDD 和收益集中度要求，因此未进入正式双倍成本候选筛选。

## 最佳近失项

最佳近失项 `lvcb-d7353834bbe0`：

- 压缩分位 `0.30`，回看 `8`
- EMA `48/192`，slope lag `8`
- Donchian `192`
- ATR cap `0.004`
- `6 ATR` 止损
- 最多持有 `48` 根，即 `12h`

| 区间 | Return | MDD | Trades | PF | 失败原因 |
| --- | ---: | ---: | ---: | ---: | --- |
| Train | `+1.07%` | `-11.44%` | `17` | `1.11` | 样本不足、单笔集中 |
| Validation | `+0.54%` | `-21.00%` | `75` | `1.04` | PF 未达到 `1.05` |
| Reused diagnostic | `-11.05%` | `-18.41%` | `105` | `0.85` | 转负 |
| Reused diagnostic 2x | `-34.98%` | `-37.73%` | `105` | `0.52` | 成本压力崩溃 |

该项在开发区间的收益已经接近噪声，且揭示 `2024+` 后明显为负，不构成近似可用候选。

## 时间稳定性

- `180d` 滚动窗口：`4/13` 正收益，仅 `30.8%`
- 正收益自然年：`3/7`
- `2024 -16.45%`
- `2025 +6.61%`
- `2026 YTD -0.15%`
- 最近 `1m -0.42%`、`3m -2.28%`、`6m -1.02%`、`1y +3.20%`

最近一年小幅为正不能覆盖开发门禁与 reused diagnostic 的失败，也不能作为读取近期数据后回调参数的理由。

## 方向裁决

使用该近失信号在 reused diagnostic 上：

- short-only：`-11.05%`
- long-only same signal：`-25.13%`
- both：`-33.41%`

这说明该参数组合本身没有稳定 edge；不是通过改成多空组合即可修复。

## 决策

1. 空头方向本轮失败，不产生候选、不登记、不 promotion。
2. 现有 `lvcb-913f4ff89386` 继续保持 long-only；不得把本轮失败空头叠加进去。
3. 停止在同一压缩/EMA/Donchian 对称空头机制上继续历史调参。
4. 若未来研究 BTC 空头，应使用与对称 breakdown 不同的独立机制，例如风险关闭或急跌后的状态机，并重新冻结防泄漏协议。

## 证据

- [机器摘要](../artifacts/btc_15m_lvcb_short_search_summary_2026-07-21.json)
- [全部候选](../artifacts/btc_15m_lvcb_short_search_candidates_2026-07-21.csv)
- [近失项逐笔交易](../artifacts/btc_15m_lvcb_short_search_trades_2026-07-21.csv)
- [180d 滚动窗口](../artifacts/btc_15m_lvcb_short_search_rolling_2026-07-21.csv)
- [复现脚本](../scripts/research_btc_15m_lvcb_short_search.py)
