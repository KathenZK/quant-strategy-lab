# HYPE ATR Trend Optimization

> 迁移说明：本文由 legacy Cursor Canvas `hype-atr-trend-optimization.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-CC legacy Canvas。

Deep search around ATR dynamic sizing plus 24h trend blocking. The base signal is unchanged.

### 关键指标

| 指标 | 数值 |
| --- | --- |
| Balanced 1Y Return | +220.50% |
| Balanced Max DD | -43.30% |
| Balanced 3M Return | +236.88% |
| Balanced 3M DD | -19.14% |

## One Year Candidates

| Candidate | ATR | Max Allocation | Target ATR | Return | Max DD | Avg Allocation |
| --- | --- | --- | --- | --- | --- | --- |
| Original ATR | ATR96 | 3.0 | 0.004 | +201.61% | -49.06% | 0.83x |
| High Return | ATR192 | 1.5 | 0.010 | +252.05% | -48.77% | 0.69x |
| Balanced | ATR192 | 2.5 | 0.004 | +220.50% | -43.30% | 0.68x |
| Lower DD | ATR192 | 3.0 | 0.003 | +198.27% | -39.90% | 0.62x |
| Conservative | ATR192 | 2.0 | 0.004 | +165.91% | -36.31% | 0.55x |

## Window Validation

| Candidate | 1Y Return | 1Y DD | 3M Return | 3M DD | 1W Return | 1W DD |
| --- | --- | --- | --- | --- | --- | --- |
| High Return | +252.05% | -48.77% | +229.06% | -15.24% | +22.47% | -7.80% |
| Balanced | +220.50% | -43.30% | +236.88% | -19.14% | +38.55% | -10.61% |
| Lower DD | +198.27% | -39.90% | +206.59% | -17.03% | +35.05% | -9.58% |
| Conservative | +165.91% | -36.31% | +168.32% | -15.39% | +29.96% | -8.55% |

## Implementation Rules

| Area | Rule | Purpose |
| --- | --- | --- |
| Signal | 10 根 15m K 线中阳线或阴线数量 >= 8 | 保持原策略不变 |
| ATR sizing | entry_allocation = min(max_allocation, max_allocation * target_atr / ATR%) | 高波动自动降仓 |
| ATR window | 192 根 15m K 线，约 48 小时 | 比 24h ATR 更平滑 |
| Trend block | 最近 96 根约 24h 涨跌超过 6% 时，不逆势开仓 | 避免强趋势里摸顶或抄底 |
| Execution | Hyperliquid taker 0.045% + 4bps slippage, mark high/low exits | 和当前回测口径一致 |

Recommendation: use Balanced first. High Return has slightly better 1Y return but barely improves 1Y drawdown versus the original ATR plan.
