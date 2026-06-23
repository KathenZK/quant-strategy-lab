# HYPE V33 收益/回撤组合回测

> 迁移说明：本文由 legacy Cursor Canvas `hype-v33-balanced-combo-backtest.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

从 V33 全参数消融中组合高收益、低回撤单因子，使用 live-realistic 成交口径回测。

## 选中组合

| 项目 | 内容 |
| --- | --- |
| 参数组合 | Target 0.020 / 0.018 + 1.5ATR MFE + 7ATR hard stop |
| 相对 V33 | 提高仓位目标；浮盈达到 1.5ATR 后关闭指标退出；硬止损从 9ATR 收紧到 7ATR |
| Binance 结果 | +5840.03%，最大回撤 -23.89%，Sharpe 4.83，交易 101 笔 |
| 判断 | 已记录为 V34：Binance 主基准候选；不作为跨交易所稳健版本 |

## 跨交易所结果

| 交易所 | 版本 | 收益 | 最大回撤 | Sharpe | 交易数 | 收益 delta | 回撤 delta |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | V33 baseline | +1650.74% | -27.49% | 4.03 | 96 | - | - |
| Binance | Selected combo | +5840.03% | -23.89% | 4.83 | 101 | +4189.29 | +3.60 |
| Hyperliquid | V33 baseline | +653.18% | -32.82% | 3.23 | 78 | - | - |
| Hyperliquid | Selected combo | +485.36% | -36.24% | 2.66 | 82 | -167.82 | -3.42 |
| OKX | V33 baseline | +456.03% | -29.18% | 2.53 | 100 | - | - |
| OKX | Selected combo | +880.42% | -30.76% | 2.83 | 104 | +424.39 | -1.58 |

## 候选对比

| 组合 | Binance 收益 | 最大回撤 | Sharpe | 交易数 | 判断 |
| --- | --- | --- | --- | --- | --- |
| Target + 1.5ATR + 7ATR | +5840.03% | -23.89% | 4.83 | 101 | Binance 最优折中，但 HL 变差 |
| Target + 7ATR stop | +4558.22% | -23.49% | 4.62 | 102 | 更简单，但 HL/OKX 回撤压力更大 |
| Moderate target + 1.5ATR + 7ATR | +4305.80% | -22.79% | 4.76 | 101 | 回撤更低，但收益少一截，HL 仍变差 |
| 1.5ATR MFE + 7ATR stop | +2937.99% | -20.46% | 4.66 | 101 | Binance 回撤最低，但 HL 明显变差 |
| Target + strict volume | +3321.49% | -27.07% | 4.32 | 95 | 三家收益都改善，但 HL/OKX 回撤变深 |
| Target 0.020 / 0.018 | +2944.16% | -33.13% | 4.17 | 96 | 三家收益都改善，但回撤不符合低回撤目标 |

## 选中组合退出结构

| 退出类型 | 次数 |
| --- | --- |
| take profit | 75 |
| indicator exit | 9 |
| stop loss | 14 |
| timeout | 2 |
| same K reentry | 0 |
