# HYPE 15m MHEF V2 连续目标仓位研究（2026-07-28）

- Family：`HYPE-15M-Multi-Horizon-EMA-Forecast`（`HYPE-15M-MHEF`）
- 研究身份：`MHEF-V2 continuous risk-target prototype`，未登记版本
- 市场：Binance USD-M `HYPEUSDT` perpetual，`15m`
- 终局结论：验证失败；状态为 `explore / not promoted / not live-ready`
- 一句话结论：找到了用户描述的经典连续趋势架构，并完整实现了“小仓试探—共振加仓—转弱减仓—成本带内不交易”，但冻结候选在未参与选择的三个月验证段毛收益 `-9.20%`、净收益 `-11.47%`，即使零成本也亏损，不能用于实盘。

## 这套策略实际做什么

1. 四条不同速度的双 EMA forecast 每根闭合 K 重算；单条 forecast 不是 `0/1` 交叉开关，而是 `[-1,1]` 连续强度。
2. 每条 forecast 用当时可见波动率和过去 expanding median 因果校准，避免“同样的均线距离”在高低波动时期代表不同强度。
3. 多周期同向时 coherence 接近 `1`，目标仓位放大；快周期先转、慢周期尚未确认时，多空 forecast 互相抵消，旧仓先减、小仓试探而不是立即反手满仓。
4. 小于 dead zone 的趋势强度归零；剩余强度再按目标年化波动缩放，且绝对仓位不超过 `1x`。
5. 当前闭合 K 只产生下一根 open 的目标仓位。实际仓位只有越出 `target ± buffer` 且累计改变量达到最小调仓量才交易，并只追到带宽边缘；单根 K 的仓位变化另有限速。

冻结候选最终使用：

- EMA：`8/32`、`16/64`、`32/128`、`64/256`
- 权重：`0.10 / 0.20 / 0.30 / 0.40`
- coherence power：`0.5`
- dead zone：`0.10`
- 目标年化波动：`60%`
- 目标仓位带宽：`0.20`
- 最小仓位改变量：`0.15`
- 单根 K 最大改变量：`0.25`
- 成本：每单位换手手续费 `0.001` + adverse slippage `0.0004`，并计实际 funding

完整冻结参数与 hash 见 [prefit candidate](../artifacts/hype_15m_mhef_v2_prefit_candidate.json)。

## 它是不是业内经典

是，组成模块都不是临时发明：

- [Moskowitz、Ooi、Pedersen 的 Time Series Momentum](https://www.aqr.com/insights/research/journal-article/time-series-momentum) 在 58 个期货/远期市场上研究自身过去收益对未来收益的预测；重点是跨市场、较慢尺度的时序动量，不是单币 15 分钟必然有效。
- [Man AHL 对不同 trend speed 的说明](https://www.man.com/insights/need-for-speed-trend-following) 明确使用多组双指数移动平均模型并做波动率缩放；同时指出越快的模型成本影响越大，真正的机构实现依赖分散的市场组合和专门执行。
- [Gârleanu–Pedersen 的动态交易模型](https://www.nber.org/papers/w15205) 的两个核心原则是面向动态 aim portfolio、只部分向目标交易；慢衰减预测器应获更高权重。这正对应本研究的慢周期高权重和分步调仓。
- [Harvey 等人的 Volatility Targeting](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID3202923_code16198.pdf?abstractid=3175538&mirid=1) 表明波动率目标普遍可降低极端收益风险，但不保证在所有资产类别提升 Sharpe。因此它是风险控制，不是凭空制造方向 alpha。
- [A Century of Evidence on Trend-Following](https://www.aqr.com/insights/research/journal-article/a-century-of-evidence-on-trend-following-investing) 的长期证据来自跨股票指数、债券、商品、外汇的组合。把同一结论外推成“HYPE 单币 15m 一定赚钱”并不成立。

所以我们可以复制架构，不能复制机构结果。机构的主要优势来自市场广度、更长历史、较低成本与组合分散，而不只是某个神奇均线参数。

## 研究治理

数据在运行前冻结：

- 标准数据湖 closed 15m bars：`40,694`
- UTC：`2025-05-30 10:30` 至 `2026-07-28 07:45`
- missing / duplicate / critical null / invalid OHLC / raw-normalized mismatch：均为 `0`
- 数据终点 exclusive：`2026-07-28 08:00`

时间边界：

| 区间 | UTC | 用途 |
| --- | --- | --- |
| Train | 起点至 `2025-10-28 08:00` | 基线、消融和选择 |
| Tune | `2025-10-28 08:00` 至 `2026-01-28 08:00` | 基线、消融和选择 |
| Prefit validation | `2026-01-28 08:00` 至 `2026-04-28 08:00` | 候选冻结后一次揭示 |
| Reused revealed OOS | `2026-04-28 08:00` 至 `2026-07-28 08:00` | 其他 HYPE 研究已看过，本研究禁止选择且未运行 |

冻结清单见 [dataset freeze](../artifacts/hype_15m_mhef_v2_dataset_freeze.json)。

## 全参数消融与开发期搜索

本轮不是只改一组均线：

- `17` 组组件消融：四个 sleeve 单独运行/逐个删除、coherence、dead zone、波动率缩放、目标带、最小调仓量、单 K 限速、精确连续目标、零成本诊断。
- `45` 组逐参数敏感性：EMA 速度、权重、波动率窗口、因果校准长度、forecast 强度、coherence、dead zone、目标波动、buffer、最小调仓量、单 K 限速。
- `432` 组信号组合；`55` 组同时满足 train/tune 毛净收益为正和最低方向活动。
- 对开发期最优的 `8` 个信号做 `480` 组执行组合；`291` 组通过开发期双段门槛。冻结候选同信号的 `60` 个执行邻域中 `35` 个通过，不是单点孤峰。

关键消融：

| 运行 | Train 净收益 | Tune 净收益 | Tune 年化换手 | 说明 |
| --- | ---: | ---: | ---: | --- |
| 概念基线 | `+12.27%` | `-4.05%` | `111.9x` | 信号有毛收益，但成本后 tune 失败 |
| 基线零成本 | `+18.94%` | `-0.19%` | `111.9x` | tune 不是纯成本问题 |
| 精确连续目标 | `-8.86%` | `-10.08%` | `354.4x` | 每根 K 追目标不可行 |
| 单 sleeve `32/128` | `+7.26%` | `+7.34%` | `189.4x` | 开发期方向有效但换手很高 |
| 冻结候选 | `+10.42%` | `+5.88%` | `57.0x` | 开发期两段通过 |

证据：[full ablation](../artifacts/hype_15m_mhef_v2_full_ablation.csv)、[parameter sensitivity](../artifacts/hype_15m_mhef_v2_parameter_sensitivity.csv)、[signal grid](../artifacts/hype_15m_mhef_v2_signal_grid.csv)、[execution grid](../artifacts/hype_15m_mhef_v2_execution_grid.csv)。

## 冻结候选与一次验证

| 区间 | 毛收益 | 净收益 | 最大回撤 | Sharpe | 年化换手 | 调仓次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | `+14.95%` | `+10.42%` | `-13.97%` | `1.05` | `65.2x` | `159` |
| Tune | `+7.93%` | `+5.88%` | `-7.38%` | `1.05` | `57.0x` | `90` |
| Prefit validation | `-9.20%` | `-11.47%` | `-13.19%` | `-1.95` | `77.0x` | `116` |

验证段同期 HYPE open-to-open 为 `+20.55%`。候选约 `48.8%` 的 bars 做多、`51.2%` 做空；简单毛 PnL 拆分中，多头约 `-7.70%`、空头约 `-1.22%`，两边都没有方向优势，上一仓位与下一根收益相关系数约 `-0.007`。这不是“反向做就好”，而是 15m forecast 在该段基本失去预测力。

成本和 bootstrap 诊断：

| 验证运行 | 净收益 | 最大回撤 | 年化换手 |
| --- | ---: | ---: | ---: |
| 零交易成本 | `-9.09%` | `-11.16%` | `77.0x` |
| 基础成本 | `-11.47%` | `-13.19%` | `77.0x` |
| 双倍成本 | `-13.79%` | `-15.17%` | `77.0x` |
| 无成本控制、精确追目标 | `-23.97%` | `-25.39%` | `450.7x` |

验证段 91 个日收益做固定 seed、7 日 moving-block bootstrap，正收益概率仅 `10.48%`，收益 `p05 / p50 / p95` 为 `-19.50% / -8.84% / +2.76%`。完整证据见 [validation summary](../artifacts/hype_15m_mhef_v2_validation_summary.json) 和 [candidate path](../artifacts/hype_15m_mhef_v2_candidate_path.parquet)。

## 终局判断

这个架构“像一个好策略”，而且成本控制层确实按预期工作，但在 HYPE 单币 15m 上没有跨阶段稳定方向 alpha。预留验证在零成本下已经为负，因此：

- 不登记 `V1`；
- 不允许根据 `2026-01-28` 至 `2026-04-28` 的失败结果回头调参；
- 不读取 `2026-04-28` 之后的复用 OOS 来挑另一个赢家；
- 不交接 runner，不进入 dry-run/live。

真正值得保留的是实现骨架，而不是这组 HYPE 参数。若继续，应另立“多市场组合 CTA”研究契约，把多周期 forecast、波动率缩放和成本带用于足够多、相关性较低的市场，并从 `2026-07-28 08:00 UTC` 之后启动全新的 outcome-blind prospective OOS。单品种 15m 再堆指标或在已揭示区间救参数，没有研究价值。

