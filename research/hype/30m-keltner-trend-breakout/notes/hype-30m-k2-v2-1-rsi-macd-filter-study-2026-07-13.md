# HYPE-30M-Keltner-Trend-Breakout-V2.1 RSI / MACD 入场过滤研究

日期：2026-07-13

版本：`HYPE-30M-Keltner-Trend-Breakout-V2.1`

状态：`registered / not promoted / not live-ready`

结论：不增加 RSI 或 MACD 过滤，V2.1 信号保持不变。

## 目标与口径

目标按优先级同时约束：

1. 胜率高于 V2.1；
2. MDD 至少改善 `0.25pp`；
3. 全样本收益至少保留 `80%`；
4. validation 胜率/MDD不退化且收益至少保留 `70%`。

数据刷新至 `2026-07-13 06:06 UTC`，共 `588697` 根连续 `1m` closed bar；raw/normalized/cache 零差异。成本为手续费 `0.001/fill`、不利滑点 `0.0004/fill`，计入 Binance funding。

所有 RSI/MACD 都在信号 bar 收盘后确认，下一根 `30m` open 入场，无未来函数。

## 搜索空间

共测试 `369` 个单独及组合过滤：

- RSI14 来源：`30m`、已收盘 `1h`；
- RSI 动量下限：`50 / 52 / 55 / 58`；
- RSI 防过热上限：`65 / 70 / 75 / 80 / 100`，空头对称；
- MACD：`12/26/9`；
- MACD 来源：`30m`、已收盘 `1h`；
- MACD 模式：hist sign、line zero、hist+zero、hist momentum；
- RSI 与 MACD 交叉组合。

满足全样本三目标：`0`。

满足全样本 + validation 全部目标：`0`。

## 刷新后基线

截至 `2026-07-13 06:06 UTC`：

| 指标 | V2.1 |
| --- | ---: |
| Return | `+4522.03%` |
| MDD | `-25.84%` |
| Sharpe | `4.17` |
| Trades | `114` |
| Win rate | `56.14%` |
| Profit factor | `2.74` |

与 7 月 10 日冻结指标的差异来自新增样本与末端未完成持仓按窗口结束强制结算，不修改 V2.1 参数身份。

## RSI 结果

最佳近似过滤：

```text
long:  已收盘 1h RSI14 >= 58
short: 已收盘 1h RSI14 <= 42
```

| 指标 | V2.1 | 1h RSI 动量过滤 |
| --- | ---: | ---: |
| Return | `+4522.03%` | `+4297.02%` |
| 收益保留 | `100%` | `95.02%` |
| MDD | `-25.84%` | `-25.84%` |
| Win rate | `56.14%` | `57.14%` |
| Trades | `114` | `112` |
| Profit factor | `2.74` | `2.76` |

它提高胜率约 `1.00pp`，但全样本 MDD 完全没有改善，因此不满足目标。

Validation 表现较好：

| 指标 | V2.1 | 1h RSI 动量过滤 |
| --- | ---: | ---: |
| Return | `+577.08%` | `+626.08%` |
| MDD | `-19.65%` | `-17.72%` |
| Win rate | `65.79%` | `67.57%` |

但新增 holdout 表现反向：

- V2.1：2 笔/末端持仓口径，`-5.23%`；
- RSI 过滤：2 笔均亏，`-10.50%`，其中一笔 SL；
- 旧 7 月 10 日 holdout 为 `-8.25%`，新增数据未修复该问题。

因此该过滤不能因 validation 漂亮就被接受。

## MACD 结果

最佳 MACD-only 行是 `30m MACD histogram > 0` 做多、`< 0` 做空，但与 V2.1 逐指标完全等价：

| 指标 | V2.1 | MACD-only |
| --- | ---: | ---: |
| Return | `+4522.03%` | `+4522.03%` |
| MDD | `-25.84%` | `-25.84%` |
| Win rate | `56.14%` | `56.14%` |
| Trades | `114` | `114` |

Keltner 突破事件已经隐含当前 MACD histogram 方向；该 MACD 条件是死过滤，没有新增信息。

RSI+MACD 排名前列与 RSI-only 逐指标相同，说明 MACD 没有提供额外筛选。

## 近似候选稳健性

对 1h RSI≥58 / ≤42 近似候选复测：

| 检查 | 结果 |
| --- | --- |
| Rolling OOS | 44 组，正收益 `97.73%`，收益中位数 `+34.63%` |
| Monte Carlo | 失败；交易重排 MDD p05 `-41.49%`，差于门槛 `-38.77%` |
| DSR(N=1000) | `0.9636`，通过 |
| Start time | 23 个起跑点均盈利，但 CAGR CV `0.690`，失败 |
| 30m phase | 失败；非原生/原生中位 CAGR 比 `14.50%`，CV `1.125` |
| 1h phase | 通过 |
| Holdout | `-10.50%`，2 笔均亏 |

RSI 确实改善了部分 validation/OOS 汇总和相位比，但仍没有解决 MDD、交易重排尾部、启动时间或 30m 边界依赖。

## 决策

- 不修改 V2.1；
- 不创建 V2.2；
- 不增加 MACD：最佳 MACD 条件是逐笔死过滤；
- 不增加 RSI：胜率改善来自少量交易筛除，但全样本 MDD不变，新增 holdout 更差。

如果继续寻找胜率提升，优先研究“亏损交易发生时的波动/流动性 regime”或仓位风险分层，而不是继续叠加经典震荡指标。

## 证据

- [研究脚本](../scripts/research_hype_30m_k2_v2_1_rsi_macd_filters.py)
- [汇总 JSON](../artifacts/hype_30m_k2_v2_1_rsi_macd_filters_2026-07-13.json)
- [搜索表](../artifacts/hype_30m_k2_v2_1_rsi_macd_filter_search_2026-07-13.csv)
- [Near-miss trades](../artifacts/hype_30m_k2_v2_1_rsi_macd_filter_trades_2026-07-13.csv)
- [Rolling OOS](../artifacts/hype_30m_k2_v2_1_rsi_macd_filter_oos_2026-07-13.csv)
- [Monte Carlo](../artifacts/hype_30m_k2_v2_1_rsi_macd_filter_mc_2026-07-13.csv)
- [Start time](../artifacts/hype_30m_k2_v2_1_rsi_macd_filter_start_2026-07-13.csv)
- [Phase](../artifacts/hype_30m_k2_v2_1_rsi_macd_filter_phase_2026-07-13.csv)
- [数据刷新证据](../artifacts/hype_1m_standard_data_lake_repair_2026-07-13.json)
