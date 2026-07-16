# HYPE-CC-V35 用 ADX/DI 替换 24h 趋势禁入诊断（2026-07-15）

## 结论

本轮不是在 V35 上叠加第二层趋势过滤，而是：

1. 删除原 `trend_window_bars=96`、`trend_block_pct=0.05`；
2. 改用 ADX 判断趋势强度、`+DI/-DI` 判断方向；
3. 保留“完全无趋势过滤”作为消融基线。

替换规则：

```text
ADX < threshold:
    趋势不明确，允许 V35 原双向反转信号

ADX >= threshold and +DI > -DI:
    只允许做多，禁止做空

ADX >= threshold and -DI > +DI:
    只允许做空，禁止做多
```

20 组预声明粗网格中，训练段相对最优是 `ADX14 >= 35`。它明显优于“完全无趋势过滤”，但训练段收益、Sharpe、最差回撤均弱于原 V35，也没有形成参数高原。最终 holdout 中：

```text
原 V35              -17.49% / MDD -36.24%
完全无趋势过滤       -42.62% / MDD -57.66%
ADX14>=35 替换版     -40.00% / MDD -54.37%
```

**结论：原 24h / 5% 趋势禁入是 V35 的关键过滤，不能由本轮 ADX/DI 规则替代。不登记 `HYPE-CC-V36`，不修改 V35 runner 或 dry-run 配置。**

## 数据与质量

| 项目 | 口径 |
| --- | --- |
| 交易所 / 市场 | Binance USD-M Futures |
| 标的 | `HYPEUSDT` 永续 |
| 周期 | `15m` |
| UTC 数据范围 | `2025-05-30 10:30` 至 `2026-07-14 11:15` |
| OHLCV / mark price | 各 39,364 根 |
| funding | 2,457 条，最大间隔 8 小时 |
| 缺失 / 重复 | OHLCV、mark、funding 均为 0 |
| 关键空值 / 非法 OHLC | 0 |
| raw / normalized 不一致 | OHLCV 与 mark 均为 0 |

运行前发现 mark 数据比 OHLCV 少 10 根，数据质量门禁中止了首次回测；随后通过 Binance `/fapi/v1/markPriceKlines` 覆盖式补齐并确认全窗口无缺口。刷新证据见
[mark-price 数据质量产物](../artifacts/hype_cc_binance_mark_15m_refresh_2026-07-14.json)。

## 指标、执行与成本

ADX/DI 使用 Wilder 风格 EWM：

```text
alpha = 1 / window
adjust = False
min_periods = window

+DI = 100 * RMA(+DM, window) / RMA(TR, window)
-DI = 100 * RMA(-DM, window) / RMA(TR, window)
ADX = RMA(100 * abs(+DI - -DI) / (+DI + -DI), window)
```

- 指标仅使用当前及以前已闭合 `15m high/low/close`。
- ADX 或 DI 未就绪、非有限值或 DI 相等时禁止开仓。
- 网格：`window=[14,28,56,96]`，`threshold=[20,25,30,35,40]`，共 20 组。
- 信号 K 闭合后确认，下一根 K open 入场。
- 入场 K 当根 mark high/low 可以触发保护价；同 K 冲突时止损优先。
- 主成本：每次成交手续费 `0.00045`，不利滑点 `0.0004`。
- 压力成本：每次成交手续费 `0.001`，不利滑点 `0.0004`。
- funding 按 Binance funding history 计入。

## V35 基线对账

原冻结窗口 `2025-05-30 10:30` 至 `2026-06-01 03:00 UTC` 精确复现：

| 指标 | 当前可复现值 |
| --- | ---: |
| 收益 | +7713.71% |
| 最大回撤 | -33.28% |
| Sharpe | 4.56 |
| 开仓 | 339 |
| 止损 / 止盈 / 提前平 | 109 / 187 / 43 |

## 训练段滚动选择窗

选择数据截止 `2026-06-01 03:00 UTC`。使用 10 个 30 天窗口，首窗前保留 70 天历史用于指标与状态 warmup。

| 方案 | 正收益窗 | 收益中位数 | Sharpe 中位数 | 回撤中位数 | 最差回撤 | 交易中位数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 原 V35 | 70% | +42.43% | 4.22 | -22.65% | -29.91% | 28.0 |
| 完全无趋势过滤 | 60% | +32.70% | 3.35 | -25.29% | -56.58% | 34.0 |
| ADX14 >= 35 替换版 | 80% | +33.46% | 3.81 | -24.45% | -49.29% | 31.5 |

`ADX14 >= 35` 相比完全无过滤提高 Sharpe、收窄最差回撤，说明 ADX/DI 确实提供了一部分风险过滤；但相对原 V35：

- 收益中位数下降约 `8.97` 个百分点；
- Sharpe 中位数从 `4.22` 降至 `3.81`；
- 最差回撤从 `-29.91%` 扩大至 `-49.29%`；
- 没有任何相邻参数同时维持原 V35 的收益、Sharpe 和最差回撤标准。

因此候选在看 holdout 前就未通过。完整网格见
[替换实验网格](../artifacts/hype_cc_v35_replace_24h_with_adx_di_grid_2026-07-15.csv)，逐窗结果见
[滚动窗口产物](../artifacts/hype_cc_v35_replace_24h_with_adx_di_rolling_2026-07-15.csv)。

## 最终 holdout

窗口：`2026-06-01 03:15` 至 `2026-07-14 11:15 UTC`。

| 方案 | 收益 | 最大回撤 | Sharpe | 开仓 | 止损 / 止盈 / 提前平 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 原 V35 | -17.49% | -36.24% | -1.49 | 39 | 19 / 13 / 6 |
| 完全无趋势过滤 | -42.62% | -57.66% | -4.47 | 49 | 26 / 16 / 6 |
| ADX14 >= 35 替换版 | -40.00% | -54.37% | -4.21 | 47 | 25 / 15 / 6 |

ADX/DI 替换版拦截了 8 次满足“无原过滤”条件的候选检查，只比完全无过滤少亏约 `2.63` 个百分点；相对原 V35仍多亏约 `22.51` 个百分点，回撤扩大约 `18.13` 个百分点。

这说明 24h / 5% 过滤捕捉的是 ADX/DI 未覆盖的中期单边位移风险，不能简单用短周期趋势强度替换。

## 最近切片

| 窗口 | 原 V35 | 无趋势过滤 | ADX14 >= 35 替换版 |
| --- | --- | --- | --- |
| 1d 收益 / 回撤 | -0.34% / -7.44% | -0.34% / -7.44% | -3.29% / -5.72% |
| 7d 收益 / 回撤 | +2.58% / -10.29% | +2.58% / -10.29% | -0.45% / -10.29% |
| 1m 收益 / 回撤 | -19.38% / -30.30% | -40.24% / -47.74% | -37.75% / -44.31% |
| 3m 收益 / 回撤 | -8.43% / -46.76% | -56.71% / -70.19% | -30.82% / -61.94% |
| 6m 收益 / 回撤 | +530.63% / -46.76% | -27.91% / -70.19% | +34.46% / -61.94% |
| 1y 收益 / 回撤 | +5980.07% / -46.76% | +422.88% / -70.19% | +1352.03% / -61.94% |

完整切片见 [recent artifact](../artifacts/hype_cc_v35_replace_24h_with_adx_di_recent_2026-07-15.csv)。

## 全窗口与成本压力

| 口径 | 原 V35 | 无趋势过滤 | ADX14 >= 35 替换版 |
| --- | ---: | ---: | ---: |
| next-open 收益 | +6647.82% | +354.53% | +1115.88% |
| next-open 最大回撤 | -46.76% | -70.19% | -61.94% |
| next-open Sharpe | 4.07 | 1.76 | 2.60 |
| next-open 开仓 | 379 | 460 | 420 |
| Binance 成本压力收益 | +3282.24% | +106.10% | +482.66% |
| Binance 成本压力最大回撤 | -49.31% | -73.06% | -64.00% |
| Binance 成本压力 Sharpe | 3.49 | 1.13 | 2.00 |

ADX/DI 在完全无过滤基础上拦截 98 次候选检查、最终少开 40 笔，证明规则不是死代码；但它仍比原 V35 多开 41 笔，回撤和风险调整收益均明显更差。

机器可读摘要见
[summary JSON](../artifacts/hype_cc_v35_replace_24h_with_adx_di_summary_2026-07-15.json)，选中候选交易见
[selected trades](../artifacts/hype_cc_v35_replace_24h_with_adx_di_selected_trades_2026-07-15.csv)。

## 决策

1. 保留 V35 原 `96` 根 / `5%` 趋势禁入。
2. 不用 ADX/DI 替换原过滤。
3. 不登记 `HYPE-CC-V36`，不修改 quant-runner 或 dry-run 配置。
4. 不按 holdout 继续缩小 ADX 网格；候选在训练段已经明显弱于原 V35。
5. 如果未来重构趋势过滤，应考虑把 24h 位移与 ADX/DI 作为不同风险维度，而不是互相替代；但此前的叠加实验也未通过，因此需先做亏损交易 regime attribution。

## 复现入口

- 替换实验脚本：[research_hype_cc_v35_replace_24h_with_adx_di.py](../scripts/research_hype_cc_v35_replace_24h_with_adx_di.py)
- ADX/DI 指标与叠加实验：[research_hype_cc_v35_adx_di_trend_block.py](../scripts/research_hype_cc_v35_adx_di_trend_block.py)
- V35 回放与数据审计：[research_hype_cc_v35_dual_ema_filter.py](../scripts/research_hype_cc_v35_dual_ema_filter.py)
- mark 补齐脚本：[fetch_hype_cc_binance_mark_15m.py](../scripts/fetch_hype_cc_binance_mark_15m.py)
- 家族主账：[hype-cc-15m-milestone-comparison.md](../hype-cc-15m-milestone-comparison.md)
- 决策日志：[decision-log.md](../decision-log.md)
