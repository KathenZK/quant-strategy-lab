# 五个 TradingView 策略的 BTC/HYPE 适配搜索

> 迁移说明：本文由 legacy Cursor Canvas `minara-five-adapted-strategies.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Legacy strategy Canvas。

使用本地数据湖 BTC/HYPE K 线，按公开规则近似重写后做参数化改造搜索。结果已扣单边 0.045% 手续费； 未计滑点、资金费，且不是 PineScript 源码级复刻。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| 搜索窗口 | 2025-05 至 2026-05 |
| 策略族 | 5 |
| 标的：BTC / HYPE | 2 |
| 最佳结构 | Kinetic |

> **核心结论**
> `Kinetic Kalman` 是这轮里最值得继续工程化的策略：BTC 最佳约 `+69.3%` / `-16.0%`，HYPE 最佳约 `+75.2%` / `-18.9%`。其余策略可以作为过滤器或备选模块， 但不适合直接作为主策略。

## 最佳适配组合

| 策略 | 标的 | 周期 | 收益 | 最大回撤 | 交易 | 稳健性 | 参数 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Kinetic Kalman | BTC | 4h | +69.3% | -16.0% | 22 | strong | gain 0.20 / lookback 200 / band 2.5 / 双向 / SL 5% TP 12% | 主候选 |
| Kinetic Kalman | HYPE | 4h | +75.2% | -18.9% | 35 | strong | gain 0.20 / lookback 150 / band 2.0 / 只做多 / SL 4% TP 12% | 主候选 |
| Hash Momentum | BTC | 4h | +52.2% | -19.3% | 28 | strong | lookback 36 / threshold 2.5 ATR / EMA100 / 双向 / SL 8% TP 20% | 可作备选 |
| Hash Momentum | HYPE | 1h | +83.6% | -35.3% | 61 | fragile | lookback 12 / threshold 3.5 ATR / EMA100 / 只做多 / SL 4% TP 10% | 收益高但回撤偏大 |
| Qullamagi EMA Breakout | HYPE | 4h | +56.8% | -24.1% | 11 | strong | EMA 10/20 + SMA 50/100/200 / box 20 / 双向 / SL 6% TP 25% | HYPE 可复查 |
| SuperTrend STRATEGY | HYPE | 1d | +16.6% | -11.0% | 7 | strong | window 10 / mult 2.5 / 只做多 / 无固定止盈止损 | 低频防守型 |
| MACD Zero-Line | BTC | 1d | +4.2% | -1.6% | 6 | watch | 12/26/9 / 只做多 / 无固定止盈止损 | 收益太低 |
| MACD Zero-Line | HYPE | 4h | +39.8% | -33.0% | 42 | fragile | 8/26/9 / 双向 / SL 8% TP 20% | 不够稳 |
| Qullamagi EMA Breakout | BTC | 4h | -1.5% | -20.8% | 6 | fail | EMA 5/15 + SMA 67/200/350 / box 20 / 双向 / SL 6% TP 25% | 不适配 BTC |

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | 最佳累计收益率 |
| --- | --- |
| BTC Kalman | 69.3 |
| HYPE Kalman | 75.2 |
| BTC Hash | 52.2 |
| HYPE Hash | 83.6 |
| HYPE Qull | 56.8 |
| HYPE ST | 16.6 |
| HYPE MACD | 39.8 |

来源：本地数据湖 Binance perpetual OHLCV；BTC 覆盖 2025-05-15 至 2026-05-27，HYPE 覆盖 2025-05-30 至 2026-05-26；主要使用 1h/4h/1d 重采样。

## 逐策略判断

| 策略 | 判断 | 原因 |
| --- | --- | --- |
| Kinetic Kalman | 推荐优先改造 | BTC/HYPE 都能跑出 60%+ 收益且回撤低于 20%，交易数也不是极低样本。 |
| Hash Momentum | 只做备选 | BTC 上可用；HYPE 虽然收益高，但回撤约 35%，更像高波动进攻模块。 |
| Qullamagi | HYPE 可继续 | HYPE 的突破结构有效，BTC 失败；适合加大级别趋势过滤后再测。 |
| SuperTrend | 低频过滤器 | 本身不适合作主策略，HYPE 低回撤版本收益有限，可做 regime filter。 |
| MACD Zero-Line | 不建议单独交易 | 低回撤版本交易少、收益低；高收益版本回撤明显放大。 |

## 产物

搜索脚本：`../../../scripts/research/minara_five_adapt_search.py`、`../../../scripts/research/minara_five_adapt_refine.py`

结果文件：`archive/reports/legacy/minara_five_adapt_btc_hype_refined.json`、 `archive/reports/legacy/minara_five_adapt_btc_hype_refined_top_by_group.csv`。
