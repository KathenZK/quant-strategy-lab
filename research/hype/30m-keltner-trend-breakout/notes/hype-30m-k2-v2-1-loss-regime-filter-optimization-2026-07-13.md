# HYPE-30M-Keltner-Trend-Breakout-V2.1 损失 Regime 过滤优化

日期：2026-07-13

基线：`HYPE-30M-Keltner-Trend-Breakout-V2.1`

研究角色：`HYPE-30M-Keltner-Trend-Breakout-V3` 冻结证据（历史研究别名：`V2.2 candidate`）

状态：`V3 registered / not promoted / not live-ready`

## 结论

波动率 regime + 突破 bar 收盘质量组合显著改善三目标：

```text
条件 1：ATR84(signal_bar) / next_open <= 1.25%

条件 2：
  多头 close_location = (close-low)/(high-low) >= 0.65
  空头 close_location = (close-low)/(high-low) <= 0.35
```

两个条件都只使用已收盘信号 bar 及更早数据；下一根 `30m` open 入场，无未来函数。

| 指标 | V2.1 刷新基线 | Regime 候选 | 变化 |
| --- | ---: | ---: | ---: |
| Return | `+4522.03%` | `+6328.98%` | `+1806.95pp` |
| MDD | `-25.84%` | `-22.68%` | 改善 `3.17pp` |
| Sharpe | `4.17` | `5.05` | `+0.88` |
| Trades | `114` | `78` | `-36` |
| Win rate | `56.14%` | `67.95%` | `+11.81pp` |
| Profit factor | `2.74` | `4.31` | `+1.57` |
| TP / SL / time / window end | `10 / 38 / 65 / 1` | `8 / 16 / 53 / 1` | SL 减少 22 笔 |

候选同时提高胜率、降低回撤且收益没有下降，但仍未通过启动时间和 30m 相位门禁。后续已按用户决定登记为 `HYPE-30M-Keltner-Trend-Breakout-V3`；状态仍为 `registered / not promoted / not live-ready`。

## 数据与成本

- Binance USDM `HYPEUSDT`。
- 完整 `1m` 数据刷新至 `2026-07-13 06:06 UTC`。
- `588697` 行；缺失、重复、OHLC/空值问题均为 `0`。
- raw/normalized/cache 零字段差异。
- 手续费 `0.001/fill`，不利滑点 `0.0004/fill`，计入 Binance funding。

## 损失 Regime 归因

V2.1 刷新基线共 114 笔，64 笔盈利、50 笔亏损。

入场 ATR84/price：

| Group | Mean | Median | P25 | P75 |
| --- | ---: | ---: | ---: | ---: |
| Winner | `0.97%` | `0.99%` | `0.78%` | `1.12%` |
| Loser | `1.24%` | `1.20%` | `0.95%` | `1.41%` |

亏损交易明显集中在更高波动入场。`1.25%` cap 位于亏损分布中部附近，同时保留大多数低波动趋势突破。

量能和成交笔数的 winner/loser 中位数差异很小，单纯 volume/trade-count 过滤不如 ATR cap 稳定。

突破质量过滤要求收盘位于方向侧 65% 区域，避免长上影/下影或突破后回落的信号。它与 ATR cap 组合后减少 22 次 SL，而不是靠放宽止损制造高胜率。

## 搜索范围

共评估 `284` 个单过滤及两两组合：

- ATR84/price 上下限；
- ATR10/ATR84 短长波动比；
- RV12/RV48；
- quote volume / 96-bar median；
- trade count / 96-bar median；
- 平均成交额 / 96-bar median；
- 突破距离 / ATR10；
- candle body/range；
- 方向化 close location；
- VWAP confirmation；
- volatility + liquidity、volatility + quality、liquidity + quality 组合。

满足全样本三目标：`53`。

同时满足全样本与 validation 目标：`8`。

## 时间分离结果

| Window | V2.1 Return / MDD / Win | 候选 Return / MDD / Win |
| --- | --- | --- |
| Prefit | `+742.98% / -25.84% / 54.93%` | `+893.45% / -22.68% / 69.57%` |
| Validation | `+577.08% / -19.65% / 65.79%` | `+582.88% / -13.58% / 70.00%` |
| Holdout | `-5.23% / 2 笔` | `-5.23% / 2 笔` |

Prefit 与 validation 均同时改善，holdout 没有恶化，但只有 2 笔且均亏，不能视为正向 OOS 证据。

## 最近分片

| Window | V2.1 Return / MDD | 候选 Return / MDD |
| --- | --- | --- |
| `1d` | `-2.45% / -2.45%` | `-2.45% / -2.45%` |
| `7d` | `-5.94% / -7.52%` | `-5.94% / -7.52%` |
| `1m` | `+25.79% / -16.50%` | `+29.52% / -13.58%` |
| `3m` | `+242.38% / -16.50%` | `+198.93% / -13.58%` |
| `6m` | `+1042.42% / -23.85%` | `+1294.59% / -13.58%` |
| `1y` | `+3289.54% / -23.85%` | `+4255.97% / -20.38%` |

除 `3m` 收益较低外，候选大多数标准分片的收益/MDD更优；最近 7d 仍为负，过滤没有消除最新亏损。

## 阈值邻域

`close_location=0.65` 不是唯一盈利点：

- ATR cap `1.25%` + close location `0.55/0.65/0.75` 均保持正收益和较低 MDD；
- ATR cap `1.50%` + close location `0.65` 也通过全部选择约束；
- 但 `0.65` 在 prefit/validation 胜率、MDD和收益保留间最均衡。

这说明候选位于一个可见邻域，不是单一针尖；仍需更多未来交易确认。

## 门禁复测

| 检查 | 候选结果 |
| --- | --- |
| Rolling OOS | 44 组正收益 `100%`，收益中位数 `+39.34%` |
| Monte Carlo | 通过；重排 MDD p05 `-30.25%`，优于门槛 `-34.02%` |
| DSR(N=1000) | `0.9995`，通过 |
| Start time | 失败；CAGR CV `0.585 > 0.5` |
| 30m phase | 失败；非原生/原生中位 CAGR 比 `13.80%`，CV `1.152` |
| 1h phase | 通过；非原生/原生比 `101.94%` |
| Holdout | `-5.23%`，2 笔均亏 |

候选修复了 V2.1 的 Monte Carlo 尾部，但没有解决启动时间与 30m bar 边界依赖。

## 决策

本报告原始结论是保留为候选观察。后续按用户决定已登记为：

`HYPE-30M-Keltner-Trend-Breakout-V3：registered / not promoted / not live-ready`

- V2.1 规格保持冻结，作为 parent 对照；
- V3 不进入 `audit` 或 runner；
- 仍需新增未来交易确认高波动过滤是否持续减少 SL。

规格：[hype-30m-keltner-trend-breakout-v3-spec.md](../specs/hype-30m-keltner-trend-breakout-v3-spec.md)。
## 证据

- [研究脚本](../scripts/research_hype_30m_k2_v2_1_loss_regime_filters.py)
- [汇总 JSON](../artifacts/hype_30m_k2_v2_1_loss_regime_filters_2026-07-13.json)
- [盈亏 regime profile](../artifacts/hype_30m_k2_v2_1_loss_regime_profile_2026-07-13.csv)
- [搜索表](../artifacts/hype_30m_k2_v2_1_loss_regime_filter_search_2026-07-13.csv)
- [候选逐笔](../artifacts/hype_30m_k2_v2_1_loss_regime_filter_trades_2026-07-13.csv)
- [Rolling OOS](../artifacts/hype_30m_k2_v2_1_loss_regime_filter_oos_2026-07-13.csv)
- [Monte Carlo](../artifacts/hype_30m_k2_v2_1_loss_regime_filter_mc_2026-07-13.csv)
- [Start time](../artifacts/hype_30m_k2_v2_1_loss_regime_filter_start_2026-07-13.csv)
- [Phase](../artifacts/hype_30m_k2_v2_1_loss_regime_filter_phase_2026-07-13.csv)
