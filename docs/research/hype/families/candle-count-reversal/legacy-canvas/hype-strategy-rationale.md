# Why The HYPE Strategy Works

> 迁移说明：本文由 legacy Cursor Canvas `hype-strategy-rationale.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-CC legacy Canvas。

基于 Hyperliquid 官方文档和公开 API 数据，对 V4/V6 这条 HYPE 15m 反转策略做机制解释。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| HYPE Open Interest | $810.7M |
| Positive Funding Share | 92.8% |
| Top Spread | 0.26 bps |
| 24h Strong Trend Bars | 7.7% |

## Documented Mechanics

| 机制 | 文档含义 | 对策略的解释 |
| --- | --- | --- |
| Funding | perp 高于 oracle 时 funding 偏正，多头付空头 | 做空过热上涨后，如果市场拥挤，多头还要付资金费 |
| Oracle | HYPE 这类主流动性在 Hyperliquid 的资产，oracle 机制更依赖本地流动性条件 | HYPE 更容易体现 Hyperliquid 场内资金行为 |
| Mark Price | mark price 用于保证金、清算和 TP/SL 触发 | 用 mark high/low 回测止盈止损是合理方向 |
| Public API | metaAndAssetCtxs、candleSnapshot、fundingHistory、l2Book 可公开查询 | 能验证 OI、成交、funding、盘口和信号行为 |

## Public Market Evidence

| 指标 | 数值 | 解释 |
| --- | --- | --- |
| 当前 OI 名义价值 | $810.7M | HYPE 上未平仓风险很大，容易形成拥挤仓位 |
| 24h 成交额 | $218.1M | 有足够交易活跃度，策略不是在死盘里拟合 |
| 24h 成交额 / OI | 0.27x | OI 相对成交额偏重，仓位挤压和反身性更明显 |
| 当前盘口价差 | 0.26 bps | 顶层盘口很紧，8.5 bps 成本假设不是离谱值 |
| Funding 为正占比 | 92.8% | 样本里多头付空头是常态，说明市场长期有做多拥挤倾向 |
| Funding 中位数 | 0.00125% / hour | 接近基础利率项，方向上偏向空头收 funding |
| ATR96 中位数 | 0.49% | V4 target ATR 0.40% 会在常态下自动降仓 |
| 24h 涨跌超过6%的K线占比 | 7.7% | 趋势禁入只过滤少数强趋势，但这些往往是反转策略最危险的时段 |

## Signal Behavior

| 观察 | 数值 | 解释 |
| --- | --- | --- |
| 过滤后信号起点 | 161 | rolling10 同色大于等于8，并带 signal_start 与反向间隔 |
| 信号后1小时平均有利变动 | +0.067% | 短线反转边际存在，但不大 |
| 信号后4小时平均有利变动 | +0.052% | 收益主要集中在短时间窗口 |
| 信号后8小时平均有利变动 | -0.101% | 持有太久后，优势开始消失 |
| 信号后24小时平均有利变动 | -0.094% | 这解释了为什么策略要止盈止损，不适合无限持仓 |

核心判断：这不是通用 BTC 反转策略，而是 HYPE 上的短线拥挤反转策略。ADX、ATR、趋势禁入和连续止损减半， 都是在避免 HYPE 从短线过热变成真正单边趋势时被反复打穿。
