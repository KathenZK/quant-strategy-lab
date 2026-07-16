# HYPE-CC-V35 1h EMA/ADX/DI 强趋势共识过滤诊断（2026-07-15）

## 结论

本轮保留 V35 原 `96` 根 / `5%` 趋势禁入，并新增仅在“已闭合 1h 强趋势共识”中禁止逆向开仓：

```text
strong_up =
    1h EMAfast > EMAslow
    and EMAfast 连续 3 个 1h 变化上升
    and ADX14 达到进入阈值
    and +DI14 > -DI14

strong_down = 对称反向

strong_up   -> 禁止做空
strong_down -> 禁止做多
neutral     -> 保留 V35 双向反转
```

ADX 使用迟滞：进入阈值为 `20/25/30`，退出阈值固定低 5；EMA 粗网格为 `24/72`、`24/96`，共 6 组。

训练段相对最优是 `1h EMA24/72 + ADX30/25`，但收益中位数与 Sharpe 均显著弱于 V35，最差回撤也略差；最终 holdout 中没有拦截任何候选信号，交易路径与 V35 完全相同。

**结论：该 1h 强趋势共识过滤未通过，不登记 `HYPE-CC-V36`，不修改 V35 runner 或 dry-run 配置。**

这不证明“逆趋势风险不存在”，而是说明 V35 当前困难交易并不集中在本轮定义的 1h EMA/ADX/DI 强趋势状态。继续放宽阈值会逐步退化为此前已经失败的宽泛顺趋势过滤。

## 数据与质量

| 项目 | 口径 |
| --- | --- |
| 交易所 / 市场 | Binance USD-M Futures |
| 标的 | `HYPEUSDT` 永续 |
| 主周期 | `15m` |
| 趋势周期 | 从完整四根 `15m` 聚合的已闭合 `1h` |
| UTC 数据范围 | `2025-05-30 10:30` 至 `2026-07-14 11:15` |
| 15m OHLCV / mark price | 各 39,364 根 |
| 完整 1h K 线 | 9,840 根 |
| funding | 2,457 条，最大间隔 8 小时 |
| 缺失 / 重复 / 关键空值 | 0 |
| raw / normalized 不一致 | 0 |

mark-price 刷新与质量证据见
[mark-price 数据质量产物](../artifacts/hype_cc_binance_mark_15m_refresh_2026-07-14.json)。

## 无前视的 1h 投影

15m K 线以开盘时间标记。每个 1h bucket 只有在四根 15m K 全部闭合后才参与指标：

```text
hourly_available_ts = hourly_bucket_start + 1h
signal_close_ts      = signal_15m_open_ts + 15m

在 signal_close_ts 只使用 available_ts <= signal_close_ts 的最新 1h 状态
```

不完整的当前小时直接排除，不使用未来 15m K 补齐。所有 EMA、ADX、DI 和状态迟滞均先在已闭合 1h 序列上计算，再按可用时间向 15m 投影。

## 指标与状态机

### EMA

```text
EMA = EWM(close, span=N, adjust=False, min_periods=N)
```

快线固定 `EMA24`，慢线为 `EMA72/EMA96`。连续上升要求快线最近 3 个差分都大于 0；连续下降对称。

### ADX / DI

```text
alpha = 1 / 14
+DI14 = 100 * RMA(+DM, 14) / RMA(TR, 14)
-DI14 = 100 * RMA(-DM, 14) / RMA(TR, 14)
ADX14 = RMA(100 * abs(+DI14 - -DI14) / (+DI14 + -DI14), 14)
```

迟滞状态：

```text
neutral -> trend: ADX >= entry_threshold
trend   -> neutral: ADX < entry_threshold - 5
```

EMA 方向、连续斜率或 DI 方向不再一致时立即回到 neutral；反向条件达到进入阈值时可切换方向。

## 执行与成本

- 保留原 V35 24h/5% 趋势禁入、10/8 信号、ATR672 仓位与 bracket、3/3 和 12/9 退出。
- 1h 共识层只影响新开仓，不改变持仓退出或 risk multiplier。
- 信号 K 闭合后确认，下一根 K open 入场。
- 入场 K 当根 mark high/low 可以触发保护价，同 K 冲突止损优先。
- 主成本：每次成交手续费 `0.00045`、不利滑点 `0.0004`。
- 压力成本：每次成交手续费 `0.001`、不利滑点 `0.0004`。
- funding 按 Binance funding history 计入。

## V35 基线对账

原冻结窗口精确复现：

| 指标 | 当前可复现值 |
| --- | ---: |
| 收益 | +7713.71% |
| 最大回撤 | -33.28% |
| Sharpe | 4.56 |
| 开仓 | 339 |
| 止损 / 止盈 / 提前平 | 109 / 187 / 43 |

## 训练段滚动选择窗

选择数据截止 `2026-06-01 03:00 UTC`，使用 10 个 30 天窗口。通过要求包括：

- 收益中位数至少保留 V35 的 80%；
- Sharpe 中位数不低于 V35；
- 最差回撤不差于 V35；
- 交易保留率至少 70%；
- 过滤器实际拦截过信号。

| 方案 | 正收益窗 | 收益中位数 | Sharpe 中位数 | 回撤中位数 | 最差回撤 | 交易中位数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V35 baseline | 70% | +42.43% | 4.22 | -22.65% | -29.91% | 28 |
| EMA24/72 ADX30/25 | 70% | +20.96% | 2.71 | -20.40% | -31.13% | 28 |
| EMA24/96 ADX30/25 | 70% | +20.96% | 2.71 | -20.40% | -31.13% | 28 |

相对最优行只保留约 49% 的收益中位数，Sharpe 从 `4.22` 降至 `2.71`，最差回撤还略微扩大。其余四组更弱，6 组均未预通过，也不存在稳健邻居。

完整网格见
[1h 共识网格](../artifacts/hype_cc_v35_1h_consensus_trend_grid_2026-07-15.csv)，逐窗结果见
[滚动窗口产物](../artifacts/hype_cc_v35_1h_consensus_trend_rolling_2026-07-15.csv)。

## 最终 holdout

窗口：`2026-06-01 03:15` 至 `2026-07-14 11:15 UTC`。

| 方案 | 收益 | 最大回撤 | Sharpe | 开仓 | 被共识层禁入 |
| --- | ---: | ---: | ---: | ---: | ---: |
| V35 baseline | -17.49% | -36.24% | -1.49 | 39 | 0 |
| EMA24/72 ADX30/25 | -17.49% | -36.24% | -1.49 | 39 | 0 |

Holdout 完全无差异。近期亏损信号没有落入该候选定义的 1h 强趋势反向状态，因此这层过滤无法解决当前问题。

## 最近切片

| 窗口 | V35 收益 / 回撤 | 共识过滤收益 / 回撤 | 判断 |
| --- | --- | --- | --- |
| 1d | -0.34% / -7.44% | -0.34% / -7.44% | 无差异 |
| 7d | +2.58% / -10.29% | +2.58% / -10.29% | 无差异 |
| 1m | -19.38% / -30.30% | -19.38% / -30.30% | 无差异 |
| 3m | -8.43% / -46.76% | -25.77% / -43.10% | 回撤略好，收益更差 |
| 6m | +530.63% / -46.76% | +340.54% / -43.10% | 回撤略好，收益下降 |
| 1y | +5980.07% / -46.76% | +3049.26% / -43.10% | 收益近乎减半 |

完整切片见
[recent artifact](../artifacts/hype_cc_v35_1h_consensus_trend_recent_2026-07-15.csv)。

## 全窗口与成本压力

| 口径 | V35 baseline | EMA24/72 ADX30/25 |
| --- | ---: | ---: |
| next-open 收益 | +6647.82% | +3113.72% |
| next-open 最大回撤 | -46.76% | -43.10% |
| next-open Sharpe | 4.07 | 3.53 |
| next-open 开仓 | 379 | 368 |
| 禁入检查 | 0 | 24 |
| Binance 成本压力收益 | +3282.24% | +1575.70% |
| Binance 成本压力最大回撤 | -49.31% | -45.96% |
| Binance 成本压力 Sharpe | 3.49 | 2.96 |

过滤器全窗口最终少开 11 笔，回撤改善约 `3.66` 个百分点，但收益减少约 53%，Sharpe 下降，且对最终 holdout 没有帮助。这不满足风险收益交换要求。

机器可读摘要见
[summary JSON](../artifacts/hype_cc_v35_1h_consensus_trend_summary_2026-07-15.json)，选中候选交易见
[selected trades](../artifacts/hype_cc_v35_1h_consensus_trend_selected_trades_2026-07-15.csv)。

## 决策

1. 不登记 `HYPE-CC-V36`。
2. 不修改 V35 runner、dry-run 配置或版本规格。
3. 保留原 24h/5% 趋势禁入。
4. 不继续降低 ADX 阈值或缩短 EMA，因为这会向已失败的宽泛顺趋势过滤退化。
5. 下一步若继续，应先对 V35 每笔亏损做趋势特征归因，验证“逆势”究竟应由价格位移、趋势效率、波动扩张、突破结构还是其他状态定义；当前三类先验过滤均未在 holdout 证明有效。

## 复现入口

- 研究脚本：[research_hype_cc_v35_1h_consensus_trend_filter.py](../scripts/research_hype_cc_v35_1h_consensus_trend_filter.py)
- V35 回放与数据审计：[research_hype_cc_v35_dual_ema_filter.py](../scripts/research_hype_cc_v35_dual_ema_filter.py)
- ADX/DI 指标实现：[research_hype_cc_v35_adx_di_trend_block.py](../scripts/research_hype_cc_v35_adx_di_trend_block.py)
- 家族主账：[hype-cc-15m-milestone-comparison.md](../hype-cc-15m-milestone-comparison.md)
- 决策日志：[decision-log.md](../decision-log.md)
