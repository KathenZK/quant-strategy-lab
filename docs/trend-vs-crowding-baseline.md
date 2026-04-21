# 趋势主线 vs 拥挤度反转基准对比

这份文档记录 `trend_confirmation` 和 `crowding_reversal` 在同一份 shared baseline 数据上的统一比较结果。

目的：

- 不再各看各的 baseline
- 让两条策略在同一数据、同一执行假设下直接对照

## 1. 使用的共享数据

当前这份对比使用的是趋势主线的 baseline 数据集：

- app 配置：`configs/app.mvp-baseline.yaml`
- 数据种子命令：

```bash
./.venv/bin/signal-lab seed-trend-mvp -c configs/app.mvp-baseline.yaml
```

说明：

- 这份 shared baseline 更偏趋势环境
- 因此这份结果更适合验证“统一比较框架是否工作”
- 不适合直接拿来证明哪条策略长期更优

## 2. 使用的比较配置

- `configs/strategy_comparison.mvp.baseline.yaml`

运行命令：

```bash
./.venv/bin/signal-lab compare-strategies --comparison-config configs/strategy_comparison.mvp.baseline.yaml -c configs/app.mvp-baseline.yaml
```

## 3. 本次比较运行

- `run_id`: `20260421T082050Z`
- 比较报告：
  - `reports/mvp-baseline/comparisons/trend_vs_crowding_on_trend_baseline/20260421T082050Z/comparison_report.md`
- 比较清单：
  - `reports/mvp-baseline/comparisons/trend_vs_crowding_on_trend_baseline/20260421T082050Z/comparison_manifest.json`

## 4. 当前结果摘要

### `trend_confirmation_mvp_baseline`

- `cumulative_return`: `0.0413`
- `annualized_return`: `0.0434`
- `sharpe`: `11.3326`
- `max_drawdown`: `-0.0027`
- `avg_turnover`: `0.0042`
- `active_period_ratio`: `0.7042`
- `avg_gross_exposure`: `0.1467`
- `avg_net_exposure`: `0.1450`
- `gross_return_sum`: `0.0174`
- `trading_cost_sum`: `0.0007`
- `funding_cost_sum`: `-0.0238`
- `top_symbol`: `BTC/USDT:USDT`
- `worst_symbol`: `SOL/USDT:USDT`

### `crowding_reversal_mvp_baseline`

- `cumulative_return`: `0.0000`
- `annualized_return`: `0.0000`
- `sharpe`: `0.0000`
- `max_drawdown`: `0.0000`
- `avg_turnover`: `0.0000`
- `active_period_ratio`: `0.0000`
- `avg_gross_exposure`: `0.0000`
- `avg_net_exposure`: `0.0000`
- `gross_return_sum`: `0.0000`
- `trading_cost_sum`: `0.0000`
- `funding_cost_sum`: `0.0000`

## 5. 结果解读

这份结果最重要的结论不是“趋势一定比反转好”，而是：

- 在 shared trend baseline 里，趋势主线可以稳定出信号
- 反转策略在当前这份趋势型环境里几乎不触发
- 这说明统一比较框架已经能区分“趋势环境适合趋势策略，未必适合拥挤度反转”

也就是说，这份结果更像：

- 一个框架验证样本
- 一个场景匹配示例

而不是：

- 两条策略最终优劣的结论

## 6. 这份比较最适合怎么用

适合：

- 检查统一比较框架能否正常运行
- 看策略在同一市场环境里的激活程度
- 检查策略是不是“没有信号也硬交易”

不适合：

- 直接判断 crowding 策略无效
- 拿这份结果决定长期资金分配

## 7. 下一步建议

如果要让这份对比更有决策价值，下一步最合适的是：

1. 做一个 shared comparison baseline 场景
   - 同时包含趋势段和拥挤反转段
2. 在同一份 shared comparison baseline 上重跑两条策略
3. 再进入多策略组合层
