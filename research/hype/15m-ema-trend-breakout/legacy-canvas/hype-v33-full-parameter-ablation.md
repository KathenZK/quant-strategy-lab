# HYPE V33 全参数消融

> 迁移说明：本文由 legacy Cursor Canvas `hype-v33-full-parameter-ablation.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

V33 = V32 信号 + live-realistic 成交口径：上一根 ATR、指标退出下一根 open、禁止同 K 回到 open 再入场。

## Baseline

Source: local data lake · full windows per exchange · exit structure = take profit / indicator exit / stop loss / timeout.

| 版本 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 多 / 空 | 退出结构 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V33 baseline | +1650.74% | -27.49% | 4.03 | 96 | 77.89% | 73 / 23 | 68 / 15 / 10 / 2 |
| Hyperliquid baseline | +653.18% | -32.82% | 3.23 | 78 | 73.08% | 55 / 23 | 55 / 11 / 8 / 4 |
| OKX baseline | +456.03% | -29.18% | 2.53 | 100 | 67.00% | 74 / 26 | 63 / 23 / 11 / 3 |

## 结论

| 类别 | 参数 | 判断 |
| --- | --- | --- |
| 继续有效 | 提高 target ATR | Binance +1293pp，HL +348pp，OKX +185pp；三家同时改善 |
| 继续有效 | 1.5ATR MFE 后关闭指标退出 | Binance +879pp，HL +59pp，OKX +137pp；比 1ATR 更适合 V33 |
| 需要谨慎 | No indicator exit | 三家都增益，但 Binance 回撤扩大到 -34.47%，更像进攻分支 |
| 旧结论失效 | 8ATR 硬止损 | V33 下不是强项；7ATR 在 Binance 好，但 HL 明显变差 |
| 明确不能动 | ADX 入场过滤 | 去掉 ADX 后 Binance -89.49%，回撤 -93.23%，交易数暴增到 968 |
| 执行结论 | K2 仍优于 K1 | Entry delay 1 bar 在 V33 下收益 +754%，比 baseline 少 897pp 且回撤更大 |

## 每组最佳 / 最差

| 组 | 最佳收益 | 收益 / delta | 最差收益 | 收益 / delta | 最佳 Sharpe |
| --- | --- | --- | --- | --- | --- |
| cooldown | Cooldown 16 | +829.52% (-821.22) | Cooldown 24 | +379.57% (-1271.17) | Cooldown 16 / 3.65 |
| costs | Half cost | +2009.98% (+359.24) | Double cost | +1104.65% (-546.09) | Half cost / 4.25 |
| direction | Long only | +905.74% (-745.00) | Short only | +83.92% (-1566.82) | Long only / 3.63 |
| entry_filter | No short 1h confirm | +1650.74% (+0.00) | No ADX entry filter | -89.49% (-1740.23) | No short 1h / 4.03 |
| entry_threshold | Volume 0.40 / 0.75 | +1818.29% (+167.55) | Long ADX 32 / Short ADX 40 | +106.76% (-1543.98) | Volume 0.40 / 0.75 / 4.17 |
| execution | Entry delay 4 bars | +928.36% (-722.38) | Entry delay 1 bar | +754.20% (-896.54) | Entry delay 4 / 3.37 |
| hard_stop | Hard stop 7ATR | +2360.34% (+709.60) | Hard stop 12ATR | +1294.43% (-356.31) | Hard stop 7ATR / 4.45 |
| indicator_exit | Disable after 1.5ATR MFE | +2529.41% (+878.67) | No MFE disable | +982.83% (-667.91) | Disable after 1.5ATR / 4.40 |
| sizing | Target ATR 0.020 / 0.018 | +2944.16% (+1293.42) | Target ATR 0.012 / 0.010 | +774.26% (-876.48) | Target ATR 0.020 / 0.018 / 4.17 |
| take_profit | TP 5.5ATR | +1076.30% (-574.44) | No take profit | +791.99% (-858.75) | TP 5.5ATR / 3.44 |
| time_exit | Timeout 384 bars | +1810.86% (+160.12) | Timeout 96 bars | +846.76% (-803.98) | Timeout 384 / 4.13 |

## Binance Top Return

| 组 | 变体 | 收益 | delta | 最大回撤 | Sharpe | 交易数 | 退出结构 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sizing | Target ATR 0.020 / 0.018 | +2944.16% | +1293.42 | -33.13% | 4.17 | 96 | 68 / 15 / 10 / 2 |
| indicator_exit | Disable after 1.5ATR MFE | +2529.41% | +878.67 | -27.49% | 4.40 | 95 | 72 / 10 / 10 / 2 |
| hard_stop | Hard stop 7ATR | +2360.34% | +709.60 | -19.41% | 4.45 | 102 | 72 / 14 / 13 / 2 |
| sizing | Target ATR 0.018 / 0.016 | +2300.51% | +649.77 | -30.72% | 4.12 | 96 | 68 / 15 / 10 / 2 |
| costs | Half cost | +2009.98% | +359.24 | -26.99% | 4.25 | 96 | 68 / 15 / 10 / 2 |
| indicator_exit | No indicator exit | +1917.49% | +266.75 | -34.47% | 3.91 | 94 | 75 / 0 / 15 / 3 |
| entry_threshold | Volume 0.40 / 0.75 | +1818.29% | +167.55 | -22.33% | 4.17 | 95 | 69 / 13 / 10 / 2 |
| time_exit | Timeout 384 bars | +1810.86% | +160.12 | -27.49% | 4.13 | 96 | 70 / 15 / 10 / 0 |

## Binance Worst Return

| 组 | 变体 | 收益 | delta | 最大回撤 | Sharpe | 交易数 |
| --- | --- | --- | --- | --- | --- | --- |
| entry_filter | No ADX entry filter | -89.49% | -1740.23 | -93.23% | -0.78 | 968 |
| direction | Short only | +83.92% | -1566.82 | -19.78% | 1.85 | 23 |
| entry_threshold | Long ADX 32 / Short ADX 40 | +106.76% | -1543.98 | -51.16% | 1.45 | 57 |
| cooldown | Cooldown 24 | +379.57% | -1271.17 | -35.43% | 2.70 | 70 |
| cooldown | Cooldown 8 | +590.37% | -1060.37 | -34.56% | 3.04 | 85 |
| execution | Entry delay 1 bar | +754.20% | -896.54 | -36.35% | 3.06 | 97 |
| sizing | Target ATR 0.012 / 0.010 | +774.26% | -876.48 | -20.82% | 3.86 | 96 |
| take_profit | No take profit | +791.99% | -858.75 | -35.59% | 2.86 | 47 |

## 跨交易所 Delta

| 组 | 变体 | Binance | HL | OKX | 平均 | 三家均改善 |
| --- | --- | --- | --- | --- | --- | --- |
| sizing | Target ATR 0.020 / 0.018 | +1293.42 | +347.66 | +185.18 | +608.75 | yes |
| indicator_exit | No indicator exit | +266.75 | +543.14 | +366.89 | +392.26 | yes |
| indicator_exit | Disable after 1.5ATR MFE | +878.67 | +59.12 | +136.86 | +358.22 | yes |
| sizing | Target ATR 0.018 / 0.016 | +649.77 | +195.21 | +114.17 | +319.72 | yes |
| costs | Half cost | +359.24 | +126.28 | +119.67 | +201.73 | yes |
| hard_stop | Hard stop 7ATR | +709.60 | -340.19 | +36.86 | +135.42 | no |
| time_exit | Timeout 384 bars | +160.12 | +33.36 | +109.14 | +100.87 | yes |
