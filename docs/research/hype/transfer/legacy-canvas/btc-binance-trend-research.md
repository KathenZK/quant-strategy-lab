# Binance BTC 15m 趋势策略研究

> 迁移说明：本文由 legacy Cursor Canvas `btc-binance-trend-research.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Cross-asset / transfer legacy Canvas。

Source: local data lake · Binance BTCUSDT perpetual 15m · 2025-05-15 to 2026-05-27 UTC.

> **结论**
> 没有找到满足「年化 50x+、最大回撤 20% 以内、胜率约 80%」的无前视趋势策略。强行调参得到的趋势评分候选全部亏损；最简单的整段常空也只有约 1.26x 年化倍数，且最大回撤约 25.3%。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| 满足全部目标的候选数 | 0 |
| 指标搜索最佳年化倍数 | 0.395x |
| 指标搜索最佳最大回撤 | 61.9% |
| 指标搜索最佳胜率 | 24.8% |

### 目标对比表

| 方案 | 年化倍数 | 最大回撤 | 胜率 | 结果 |
| --- | --- | --- | --- | --- |
| 目标约束 | 50x+ | <= 20% | 约 80% | 硬目标 |
| 指标搜索最佳 | 0.395x | 61.9% | 24.8% | 未通过 |
| 买入持有 | 0.736x | 52.2% | 0.0% | 未通过 |
| 整段常空 sanity | 1.260x | 25.3% | 100.0% | 未通过 |

## 月度权益曲线

> 图表数据未能完全自动解析，请按源 Canvas 复核。

Chart: end-of-month equity multiple. X-axis: month. Y-axis: equity multiple. Source: reports/btc_trend_strategy_equity.csv and Binance BTC 15m close series.

### 年化倍数对比

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Annualized equity multiple |
| --- | --- |
| 目标 | 50 |
| 指标搜索最佳 | 0.395 |
| 买入持有 | 0.736 |
| 整段常空 | 1.26 |

Chart: annualized equity multiple. X-axis: strategy. Y-axis: annualized multiple. Source: local backtest, 2025-05-15 to 2026-05-27.

### 最大回撤幅度对比

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Maximum drawdown magnitude |
| --- | --- |
| 目标上限 | 20 |
| 指标搜索最佳 | 61.9 |
| 买入持有 | 52.2 |
| 整段常空 | 25.3 |

Chart: maximum drawdown magnitude. X-axis: strategy or constraint. Y-axis: drawdown percentage. Source: local backtest and sanity checks.

### 研究方法与可复核假设

| 项目 | 说明 |
| --- | --- |
| 数据 | Binance BTCUSDT 永续 15m parquet，2025-05-15 至 2026-05-27，36210 根，15m 无缺口 |
| 执行 | 信号只用已收盘 K 线，下一根开盘成交；手续费 4 bps/边，滑点 1 bps/边 |
| 确认周期 | 基于同一 15m 数据重采样 1h/4h，避免混入不同覆盖范围 |
| 指标族 | EMA/SMA、RSI、MACD、KDJ、ATR、ADX/DMI、Donchian、Bollinger z、CCI、Williams %R、MFI、CMF、OBV、ROC、Volume z |
| 搜索规模 | 350 组信号抽样，8 个入围信号，896 组风险参数；满足目标数量为 0 |

> **数据覆盖限制**
> 用户要求最近两年 15m 数据，但本地数据湖中 BTCUSDT 永续 15m 只覆盖约 377 天。1h BTC 有更长历史，但不能替代缺失的 15m 样本；本次没有外部抓取补齐数据。

## 自动转换复核提示

以下组件存在降级转换提示，建议人工抽查源 Canvas：

- `chart`
