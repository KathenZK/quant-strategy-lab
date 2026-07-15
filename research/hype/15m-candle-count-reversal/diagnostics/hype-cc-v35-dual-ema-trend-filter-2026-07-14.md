# HYPE-CC-V35 双 EMA 趋势禁入诊断（2026-07-14）

## 结论

本轮在 `HYPE-Candle-Count-Reversal-V35` 上保留原 `96` 根 / `5%` 趋势过滤，再增加双 EMA 方向门：

- 快线高于慢线时只允许做多；
- 快线低于慢线时只允许做空；
- 均线相等或未完成 warmup 时禁止开仓。

预先声明的 13 组 EMA 组合中，`EMA24/672` 是训练段滚动 OOS 下的相对最优行。它轻微改善了 `2026-06-01 03:15 UTC` 之后的 holdout 回撤，但最近 `1m/3m` 收益仍略弱于 V35；其训练段 OOS 收益、Sharpe 与最差回撤均弱于 V35，长期收益衰减明显。

**结论：双 EMA 方向禁入未通过。本轮不登记 `HYPE-CC-V36`，不修改现有 V35 runner 或 dry-run 配置。**

这不是“均线周期还没调到最好”的证据。V35 是同色 K 极端后的反转策略，而严格要求开仓方向与快慢 EMA 趋势一致，会系统性删除其核心反转交易。继续细调 EMA 周期容易把 6 月以来已知亏损段拟合成新的样本内尖点。

## 数据与质量

| 项目 | 口径 |
| --- | --- |
| 交易所 / 市场 | Binance USD-M Futures |
| 标的 | `HYPEUSDT` 永续 |
| 周期 | `15m` |
| UTC 数据范围 | `2025-05-30 10:30` 至 `2026-07-14 11:15` |
| OHLCV | 39,364 根已闭合 K 线 |
| mark price | Binance `/fapi/v1/markPriceKlines`，39,364 根 |
| funding | 2,457 条，最大间隔 8 小时 |
| 缺失 / 重复 | OHLCV 与 mark 均为 0 |
| 关键空值 / 非法 OHLC | 0 |
| raw / normalized 不一致 | OHLCV 与 mark 均为 0 |

本轮先通过公开 Binance API 补齐并重审 mark-price 数据。刷新证据见
[mark-price 数据质量产物](../artifacts/hype_cc_binance_mark_15m_refresh_2026-07-14.json)。

## 回测口径

### EMA 定义

```text
alpha = 2 / (span + 1)
ema = pandas.Series.ewm(
    span=span,
    adjust=False,
    min_periods=span,
).mean()
```

EMA 只使用当前及以前已闭合 `15m close`。在信号 K 收盘时判断：

```text
long  allowed iff fast_ema[t] > slow_ema[t]
short allowed iff fast_ema[t] < slow_ema[t]
equal / NaN -> block
```

原 V35 `trend_window_bars=96`、`trend_block_pct=0.05` 过滤继续保留。EMA 只影响新开仓，不影响持仓退出、ATR、仓位或连续止损降仓状态。

### 预声明网格

```text
fast = [24, 48, 96, 192]
slow = [96, 192, 384, 672]
仅测试 fast < slow，共 13 组
```

### 执行与成本

- 基线 parity：信号 K close 入场，仅用于对照冻结 V35 回放。
- 候选选择：信号 K 闭合后确认，下一根 K open 入场；入场 K 当根 mark high/low 可触发保护价。
- 止盈止损：Binance `15m` mark high/low；同 K 冲突时止损优先。
- 主成本：每次成交手续费 `0.00045`，不利滑点 `0.0004`。
- 成本压力：每次成交手续费 `0.001`，不利滑点 `0.0004`。
- funding：按 Binance funding history 计入。

### 选择与 holdout

- 选择数据只使用至 `2026-06-01 03:00 UTC`。
- 滚动 OOS：`60d` 历史 + `10d` gap + `30d` OOS，按 30 天推进，共 10 窗。
- `2026-06-01 03:15` 至 `2026-07-14 11:15 UTC` 是最终 holdout，不参与均线选择。
- 最近 `1d/7d/1m/3m/6m/1y` 仅作审计，不参与选参。

## V35 基线 parity

当前冻结回放可精确复现家族文档已记录的本地基线：

| 指标 | 当前可复现值 |
| --- | ---: |
| 收益 | +7713.71% |
| 最大回撤 | -33.28% |
| Sharpe | 4.56 |
| 开仓 | 339 |
| 止损 / 止盈 / 提前平 | 109 / 187 / 43 |

旧规格中的 `340` 笔 / `+8357.56%` 不能由当前冻结回放重现；该差异已经在家族里程碑的“V35 本地复现基准”记录。本轮使用 339 笔可复现基线，不用旧 headline 决定候选是否通过。

## 滚动 OOS 结果

| 方案 | 正收益窗 | 收益中位数 | Sharpe 中位数 | 回撤中位数 | 最差回撤 | 交易中位数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V35 baseline | 70% | +42.43% | 4.22 | -22.65% | -29.91% | 28 |
| EMA24/672 | 60% | +26.49% | 3.37 | -22.50% | -32.22% | 20 |
| EMA48/672 | 60% | +19.14% | 2.94 | -25.13% | -32.12% | 19.5 |
| EMA48/384 | 70% | +19.43% | 2.93 | -23.63% | -33.46% | 20 |
| EMA96/192 | 70% | +19.66% | 2.91 | -24.06% | -29.31% | 20 |

`EMA24/672` 虽然在粗网格中有两个同方向邻居，但它仍同时输给 V35 的 OOS 收益中位数、Sharpe 中位数和最差回撤，因此训练段预通过为失败。完整 13 组结果见
[EMA 网格](../artifacts/hype_cc_v35_dual_ema_grid_2026-07-14.csv) 与
[逐窗 OOS](../artifacts/hype_cc_v35_dual_ema_oos_2026-07-14.csv)。

## Holdout

| 方案 | 收益 | 最大回撤 | Sharpe | 开仓 | 止损 / 止盈 / 提前平 |
| --- | ---: | ---: | ---: | ---: | ---: |
| V35 baseline | -17.49% | -36.24% | -1.49 | 39 | 19 / 13 / 6 |
| EMA24/672 | -16.98% | -34.70% | -1.62 | 33 | 15 / 13 / 4 |

EMA 方向门在已知困难期只少亏约 `0.51` 个百分点，回撤收窄约 `1.54` 个百分点，并阻止 13 次候选入场。Holdout 仍为负收益，Sharpe 反而更低；且该研究动机本身来自已知 live / OOS 亏损，不能把这段轻微改善当作全新、未观察数据上的确认。

## 最近切片

| 窗口 | V35 收益 / 回撤 | EMA24/672 收益 / 回撤 | 判断 |
| --- | --- | --- | --- |
| 1d | -0.34% / -7.44% | -3.29% / -5.72% | 各 1 笔未平仓，证据很弱 |
| 7d | +2.58% / -10.29% | -0.45% / -10.29% | EMA 较差；仅 4 笔 |
| 1m | -19.38% / -30.30% | -19.87% / -28.61% | 回撤略好，收益略差 |
| 3m | -8.43% / -46.76% | -9.30% / -34.70% | 回撤改善，收益略差 |
| 6m | +530.63% / -46.76% | +86.78% / -34.70% | 回撤改善但收益大幅衰减 |
| 1y | +5980.07% / -46.76% | +370.33% / -41.35% | 长期收益与 Sharpe 明显受损 |

完整最近切片见 [recent artifact](../artifacts/hype_cc_v35_dual_ema_recent_2026-07-14.csv)。

## 全窗口与成本压力

| 口径 | V35 baseline | EMA24/672 |
| --- | ---: | ---: |
| next-open 收益 | +6647.82% | +427.25% |
| next-open 最大回撤 | -46.76% | -41.35% |
| next-open Sharpe | 4.07 | 2.07 |
| next-open 开仓 | 379 | 285 |
| Binance 成本压力收益 | +3282.24% | +212.26% |
| Binance 成本压力最大回撤 | -49.31% | -43.55% |
| Binance 成本压力 Sharpe | 3.49 | 1.56 |

全窗口中 EMA24/672 拦截 216 次通过原趋势过滤的信号检查，最终少开 94 笔。回撤只改善约 5.4 个百分点，但主成本下收益从 `+6648%` 降到 `+427%`，成本压力下进一步降至 `+212%`。这不是合理的风险收益交换。

选中候选的交易明细见
[selected trades](../artifacts/hype_cc_v35_dual_ema_selected_trades_2026-07-14.csv)，完整机器可读摘要见
[summary JSON](../artifacts/hype_cc_v35_dual_ema_summary_2026-07-14.json)。

## 决策

1. 不登记 `HYPE-CC-V36`。
2. 不修改 V35 的参数规格、quant-runner 策略实现或 dry-run 配置。
3. 不继续围绕 6 月亏损段细调 EMA 周期；这会增加二次过拟合风险。
4. 如果继续研究趋势过滤，应回到 V35 过拟合诊断建议的 regime split 或更少后期增强层的基线，而不是把严格顺趋势条件叠加在反转入场之上。

## 复现入口

- 研究脚本：[research_hype_cc_v35_dual_ema_filter.py](../scripts/research_hype_cc_v35_dual_ema_filter.py)
- mark 补齐脚本：[fetch_hype_cc_binance_mark_15m.py](../scripts/fetch_hype_cc_binance_mark_15m.py)
- 家族主账：[hype-cc-15m-milestone-comparison.md](../hype-cc-15m-milestone-comparison.md)
- 决策日志：[decision-log.md](../decision-log.md)
