# Minara 21 个 TradingView 策略页面定位结果

> 迁移说明：本文由 legacy Cursor Canvas `minara-tradingview-scripts-found.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Legacy strategy Canvas。

我按原文榜单逐个查了 TradingView 社区库。这里记录的是能从公开网页拿到的页面、开源标记和规则摘要。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| 找到精确脚本页 | 20 / 21 |
| 只找到搜索页条目 | 1 / 21 |
| 页面标记 OPEN-SOURCE | 多数开源 |
| TradingView 无官方 API | 源码未批量下载 |

> **重要限制**
> 当前能从公开网页稳定拿到“说明”和“开源/保护状态”，但拿不到完整 PineScript 源码。TradingView 的源码需要在页面里点 `Source code` 或加载到 Pine Editor；没有官方免登录 API。Protected / invite-only 不能抓源码。

## 逐个定位结果

> 表格数据未能完全自动解析，请按源 Canvas 复核。

## 下一步建议

可先复现规则最清楚的开源页：`MACD Zero-Line`、`RSI > 70`、 `SuperTrend STRATEGY`、`7/19 EMA`、`ETH Keltner`、 `Kinetic Kalman`。

对于复杂策略，最好让 TradingView 打开源码后贴给我，或者手动导出 PineScript；否则只能按页面说明近似重写，结果不能叫严格复现。

## 自动转换复核提示

以下数据数组包含 TypeScript 对象、表达式或 JSX，未必全部进入正文表格：

- `rows`

以下组件存在降级转换提示，建议人工抽查源 Canvas：

- `table`
