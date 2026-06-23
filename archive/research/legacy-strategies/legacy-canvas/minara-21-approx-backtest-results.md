# Minara 21 个策略 BTC/HYPE 近似回测

> 迁移说明：本文由 legacy Cursor Canvas `minara-21-approx-backtest-results.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Legacy strategy Canvas。

这是按公开 TradingView 页面说明重写的近似规则，不是逐笔 PineScript 复刻。每个策略都分别跑了 BTC 与 HYPE。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| 回测组合数：21策略 x 2标的 | 42 |
| 正收益组合数 | 11 |
| 零交易/无信号组合 | 7 |
| 最值得优先核源码策略数 | 1 |

> **先看这个**
> 最亮眼的是 HYPE 上的 Moon Phases，但它规则可信度低，不建议当作候选。更值得继续深挖的是 `Kinetic Kalman`、`MACD Zero-Line`、`SuperTrend STRATEGY` 和 BTC 上的 `Qullamagi`/`Hash Momentum`，但都需要拿 Pine 源码后再严格复现。

## 正收益组合排行

| 策略 | 标的 | 收益 | 最大回撤 | 规则质量 | 备注 |
| --- | --- | --- | --- | --- | --- |
| Moon Phases | HYPE | +70.65% | -21.25% | 低 | 另类月相规则，不能直接信 |
| Kinetic Kalman | HYPE | +18.82% | -31.54% | 中 | 可复查 Pine 源码后再跑 |
| Hash Supertrend | HYPE | +17.85% | -54.81% | 中 | 回撤过大 |
| Moon Phases | BTC | +14.09% | -24.94% | 低 | 解释性弱 |
| SuperTrend STRATEGY | HYPE | +14.04% | -0.05% | 高 | 交易数只有2笔 |
| Qullamagi EMA Breakout | BTC | +11.89% | -30.46% | 中 | 可继续优化风控 |
| Hash Momentum | BTC | +10.43% | -29.56% | 中 | 正收益但回撤大 |

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | 累计收益率 |
| --- | --- |
| Moon HYPE | 70.65 |
| Kalman HYPE | 18.82 |
| Hash ST HYPE | 17.85 |
| Moon BTC | 14.09 |
| ST HYPE | 14.04 |
| Qullamagi BTC | 11.89 |
| Hash Mom BTC | 10.43 |

来源：本地数据湖 Binance perp；BTC/HYPE 以 15m 为基础，高周期重采样；HYPE 5m 使用原生 5m，BTC 5m 用 15m 代理。

## 逐一结果

| # | 策略 | 规则质量 | BTC 收益 / DD / 交易 | HYPE 收益 / DD / 交易 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | RSI 20/65 均值回归 | 中 | BTC -16.53% / -24.15% / 10 | HYPE -11.30% / -13.98% / 10 | 最近90天不通过 |
| 2 | Volatility Breakout | 中 | BTC -17.52% / -28.79% / 188 | HYPE -20.63% / -50.19% / 168 | 过度交易，成本和假突破重 |
| 3 | SuperTrend AI Adaptive | 低 | BTC -18.92% / -30.48% / 30 | HYPE -1.79% / -61.77% / 28 | HYPE收益接近持平但回撤很大 |
| 4 | BB Upper Short +2% | 中 | BTC 0.00% / 0.00% / 0 | HYPE -13.77% / -22.07% / 14 | BTC无信号，HYPE高胜率但亏 |
| 5 | SuperTrend STRATEGY | 高 | BTC +1.08% / -0.05% / 1 | HYPE +14.04% / -0.05% / 2 | 低频，样本太少 |
| 6 | Penguin Volatility State | 中 | BTC -5.65% / -27.75% / 8 | HYPE -40.35% / -77.98% / 5 | 不适合当前 HYPE 窗口 |
| 7 | MACD Zero-Line Long Only | 高 | BTC +4.24% / -1.60% / 6 | HYPE +9.14% / -0.05% / 3 | 低频可继续复查 |
| 8 | CDC MACD fixed amount | 高 | BTC +5.22% / -10.16% / 8 | HYPE -23.52% / -24.55% / 4 | BTC可，HYPE不适配 |
| 9 | Hash Momentum | 中 | BTC +10.43% / -29.56% / 103 | HYPE -53.80% / -64.73% / 220 | BTC正但回撤大，HYPE失败 |
| 10 | Moon Phases Long/Short | 低 | BTC +14.09% / -24.94% / 15 | HYPE +70.65% / -21.25% / 24 | 结果好但规则可信度低 |
| 11 | 7/19 EMA | 高 | BTC -18.78% / -27.20% / 470 | HYPE -87.60% / -88.77% / 495 | 交易太多，被成本打穿 |
| 12 | RSI > 70 Buy | 高 | BTC -1.66% / -6.76% / 34 | HYPE -15.34% / -15.34% / 37 | BTC接近持平，HYPE不行 |
| 13 | 50/200 SMA + RSI Avg | 中 | BTC 0.00% / 0.00% / 0 | HYPE -5.32% / -23.20% / 3 | BTC无信号，样本不足 |
| 14 | Kadunagra Pivot SuperTrend | 低 | BTC -9.36% / -30.07% / 38 | HYPE -42.26% / -57.91% / 55 | 近似规则失败 |
| 15 | ETH Keltner Breakout | 中 | BTC -12.81% / -13.13% / 111 | HYPE -5.43% / -26.77% / 97 | 方向不稳，交易偏多 |
| 16 | Hash Supertrend | 中 | BTC -28.73% / -39.75% / 33 | HYPE +17.85% / -54.81% / 26 | HYPE正但回撤过大 |
| 17 | Crypto LONG PY | 低 | BTC 0.00% / 0.00% / 0 | HYPE 0.00% / 0.00% / 0 | 公开描述不足，近似规则无信号 |
| 18 | Oleg_Aryukov | 中 | BTC 0.00% / 0.00% / 0 | HYPE 0.00% / 0.00% / 0 | 近似条件太严，无信号 |
| 19 | Daily Long 08:30 Exit 08:00 | 高 | BTC -4.72% / -4.75% / 60 | HYPE -4.53% / -4.62% / 60 | 时间规则亏损 |
| 20 | Qullamagi EMA Breakout | 中 | BTC +11.89% / -30.46% / 30 | HYPE -2.71% / -29.03% / 49 | BTC正但回撤大 |
| 21 | Kinetic Kalman Breakout | 中 | BTC -2.16% / -13.52% / 115 | HYPE +18.82% / -31.54% / 109 | HYPE正但波动大 |

## 产物

脚本：`reports/minara_21_approx_backtest.py`

结果：`reports/minara_21_approx_btc_hype.json`、 `reports/minara_21_approx_btc_hype_summary.csv`、 `reports/minara_21_approx_btc_hype_trades.csv`。
