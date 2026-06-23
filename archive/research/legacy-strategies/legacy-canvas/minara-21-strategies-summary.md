# Minara 文中 21 个“印钞机”策略概览

> 迁移说明：本文由 legacy Cursor Canvas `minara-21-strategies-summary.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Legacy strategy Canvas。

这是对 X 长文中 Tier 1 策略的中文整理：它们都通过了 Minara 的 TradingView 复现验证，并在 HyperLiquid 费率下年化超过 10%。注意：我本地只复现回测了排名第一的 RSI 20/65 规则。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| 原文 Tier 1 策略数 | 21 |
| 原文最高年化 | +204.6% |
| 原文最核心结论 | 低频优先 |
| 排名第一最近90天本地验证 | 未复现 |

> **先说结论**
> 这 21 个不是同一种圣杯策略。真正共性是交易频率和单笔收益能覆盖手续费。趋势/突破类占多数； 均值回归能上榜的，基本都是低频或单笔利润足够厚。高频、小利润策略最容易从盈利变亏损。

## 21 个策略逐个情况

| # | 策略 | 标的/周期 | 原文年化 | 类型 | 怎么看 |
| --- | --- | --- | --- | --- | --- |
| 1 | Optimized BTC Mean Reversion (RSI 20/65) | BTC 15m | +204.6% | 均值回归 | 低频，90天仅约16笔；本地复现最近90天未通过，BTC/HYPE 都亏损。 |
| 2 | Volatility Breakout System [Fixed Risk] | ETH 1h | +124.6% | 波动突破 | 动量/突破型，收益高但依赖趋势延续。 |
| 3 | SuperTrend AI Adaptive - Strategy [BTC] | BTC 4h | +60.2% | 趋势跟踪 | 胜率不高，但靠大行情覆盖小亏。 |
| 4 | BB Upper breakout Short +2% (dr Ziuber) | SOL 1h | +48.1% | 均值回归做空 | 49笔全胜但样本小，最大回撤约36.7%。 |
| 5 | SuperTrend STRATEGY | BTC 1d | +35.6% | 超低频趋势 | 4年仅数笔，费率影响极低，但最大回撤可到约46%。 |
| 6 | Penguin Volatility State Strategy | BTC 1d | +34.5% | 波动状态 | 日线低频，偏趋势/波动 regime。 |
| 7 | MACD Zero-Line Strategy (Long Only) | BTC 1d | +34.5% | MACD 只做多 | 吃 BTC 长期 beta，弱势期靠空仓过滤。 |
| 8 | CDC BACKTEST (MACD) FIX AMOUNT | BTC 1d | +34.5% | MACD 固定金额 | 和 MACD 日线趋势框架接近，低交易频率是关键。 |
| 9 | Hash Momentum Strategy | BTC 4h | +32.8% | 动量 | 中低频趋势延续，靠少数大赢家。 |
| 10 | Moon Phases Long/Short Strategy | BTC 1h | +29.9% | 日历/另类信号 | 信号解释性弱，需警惕偶然相关。 |
| 11 | 7/19 EMA Crypto strategy | ETH 30m | +28.4% | EMA 趋势 | 比日线更频繁，手续费开始更重要。 |
| 12 | RSI > 70 Buy / Exit Cross Below 70 | BTC 4h | +24.3% | RSI 动量 | 反直觉：超买买入；胜率约35%，但回撤约14.8%。 |
| 13 | 50 & 200 SMA + RSI Average Strategy | ETH 1d | +23.5% | 趋势过滤只做多 | 买持 ETH 亏损期仍跑赢，优势在少交易和弱势空仓。 |
| 14 | Kadunagra Pivot Point SuperTrend | BTC 4h | +23.2% | Pivot + SuperTrend | 趋势跟踪变体，表现取决于 BTC 4h regime。 |
| 15 | ETHUSDT 4H - Keltner Breakout | ETH 4h | +21.0% | Keltner 突破 | 胜率约34%，典型低胜率高盈亏比。 |
| 16 | Hash Supertrend [Hash Capital Research] | SOL 4h | +15.2% | SuperTrend | SOL 样本更少，资产特异性更强。 |
| 17 | Crypto LONG PY | SOL 5m | +12.2% | 短线均值回归/只做多 | 39笔胜率100%，但 5m 策略对手续费敏感。 |
| 18 | Oleg_Aryukov_Strategy | BTC 15m | +10.9% | 未详述 | 刚过 Tier 1 门槛，需要看交易次数和源码。 |
| 19 | Options test Daily Long 08:30 Exit 08:00 UTC | ETH 5m | +10.8% | 日内时间规则 | 更像时间窗口效应，实盘要检验时区和执行。 |
| 20 | Qullamagi EMA Breakout Autotrade | ETH 1h | +10.5% | EMA 突破 | 趋势突破框架，边际收益不厚。 |
| 21 | Kinetic Kalman Breakout | ETH 15m | +10.1% | Kalman 突破 | 刚过线，15m 频率下成本和滑点风险较大。 |

## 按类型拆开看

| 类型 | 数量 | 代表 | 关键风险 |
| --- | --- | --- | --- |
| 趋势 / 突破 / 动量 | 约 13 个 | SuperTrend、EMA、Keltner、MACD、RSI 动量等 | 多数胜率不高，靠少数大赢家。 |
| 均值回归 | 约 4 个 | RSI 20/65、BB Upper Short、Crypto LONG PY 等 | 交易要足够少，否则手续费吃掉优势。 |
| 另类 / 时间规则 | 约 2 个 | Moon Phases、固定时间入场退出 | 最需要样本外验证。 |
| 未充分披露 | 约 2 个 | Oleg_Aryukov、部分 Hash/Penguin 细节 | 只有名称和榜单指标，不能直接实盘。 |

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | 策略数量 |
| --- | --- |
| 趋势/突破 | 13 |
| 均值回归 | 4 |
| 另类/时间 | 2 |
| 未详述 | 2 |

数量是根据原文描述和策略名称做的粗分类，不等同于源码审计。

## 对我们下一步有用的筛选

优先值得本地复现：BTC/ETH/SOL 上低频、规则清楚的策略，比如 SuperTrend、Keltner Breakout、RSI > 70 动量、50/200 SMA + RSI。

暂时不要直接信：胜率 100% 但交易数很少的策略、Moon Phases 这类解释性弱的信号、刚过 10% 门槛的 15m/5m 策略。

已经本地验证过的排名第一策略脚本在 `reports/minara_rsi2065_btc_hype_backtest.py`； 结果显示它在 BTC/HYPE 最近 90 天没有复现原文强表现。
