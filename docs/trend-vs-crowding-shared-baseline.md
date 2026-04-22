# 趋势主线 vs 拥挤度反转共享基准对比

这份文档记录 `trend_confirmation` 和 `crowding_reversal` 在同一份 regime-mixed shared baseline 数据上的统一比较结果。

这份结果比单独的 trend-only baseline 更有参考价值，因为它在一份数据里同时包含：

- 趋势延续段
- 拥挤积累段
- 短周期反转段

## 1. 使用的共享数据

当前这份对比使用的是共享比较 baseline 数据集：

- app 配置：`configs/app.shared-comparison-baseline.yaml`
- 数据种子命令：

```bash
./.venv/bin/signal-lab seed-shared-comparison-mvp -c configs/app.shared-comparison-baseline.yaml
```

说明：

- 这份 shared baseline 不是纯趋势环境
- 也不是纯反转环境
- 它的目标是让两条策略在同一份数据里都能被激活

## 2. 使用的比较配置

- `configs/strategy_comparison.shared-baseline.yaml`

运行命令：

```bash
./.venv/bin/signal-lab compare-strategies --comparison-config configs/strategy_comparison.shared-baseline.yaml -c configs/app.shared-comparison-baseline.yaml
```

或者使用统一 batch 入口：

```bash
./.venv/bin/signal-lab run-batch --mode comparison --batch-config configs/strategy_comparison.shared-baseline.yaml -c configs/app.shared-comparison-baseline.yaml
```

## 3. 本次比较运行

- `run_id`: `20260421T083145Z`
- 比较报告：
  - `reports/shared-comparison-baseline/comparisons/trend_vs_crowding_on_shared_baseline/20260421T083145Z/comparison_report.md`
- 比较清单：
  - `reports/shared-comparison-baseline/comparisons/trend_vs_crowding_on_shared_baseline/20260421T083145Z/comparison_manifest.json`
- registry 索引：
  - `reports/shared-comparison-baseline/_registry/runs.jsonl`

## 4. 当前结果摘要

### `trend_confirmation_mvp_shared_baseline`

- `cumulative_return`: `0.0382`
- `annualized_return`: `0.0300`
- `sharpe`: `4.9648`
- `max_drawdown`: `-0.0088`
- `avg_turnover`: `0.0238`
- `active_period_ratio`: `0.7406`
- `avg_gross_exposure`: `0.1794`
- `avg_net_exposure`: `0.1281`
- `gross_return_sum`: `0.0056`
- `trading_cost_sum`: `0.0053`
- `funding_cost_sum`: `-0.0373`
- `top_symbol`: `BTC/USDT:USDT`
- `worst_symbol`: `SOL/USDT:USDT`

### `crowding_reversal_mvp_shared_baseline`

- `cumulative_return`: `-0.0069`
- `annualized_return`: `-0.0055`
- `sharpe`: `-3.3422`
- `max_drawdown`: `-0.0069`
- `avg_turnover`: `0.0019`
- `active_period_ratio`: `0.0469`
- `avg_gross_exposure`: `0.0138`
- `avg_net_exposure`: `-0.0038`
- `gross_return_sum`: `0.0036`
- `trading_cost_sum`: `0.0004`
- `funding_cost_sum`: `0.0102`
- `top_symbol`: `ETH/USDT:USDT`
- `worst_symbol`: `SOL/USDT:USDT`

## 5. 结果解读

这份 shared baseline 的价值在于，它终于让两条策略在同一份数据里都产生了行为：

- `trend_confirmation` 明显更活跃，持仓期更长，收益主导来自 `BTC`
- `crowding_reversal` 确实被激活，但只在较短区间参与，活跃期明显更低
- `crowding_reversal` 的毛收益为正，但在这份场景里被资金费率和交易成本吃掉，最终净值为负

这说明：

- 趋势主线当前更适合作为核心主策略
- 拥挤度反转更像补充策略，而不是主线替代者
- 如果后面要让反转策略更有竞争力，重点不是盲目加杠杆，而是优化：
  - 触发阈值
  - 反转确认条件
  - 资金费率惩罚处理
  - liquidation 风险层的配合

## 6. 当前可用结论

这份 shared baseline 已经能支持下面这些判断：

- 哪条策略在混合市场状态下更稳定
- 哪条策略更容易被交易成本和 funding 吞噬
- 哪条策略更偏“常驻型”，哪条更偏“择时型”

当前结论是：

- `trend_confirmation` 更适合作为核心 alpha
- `crowding_reversal` 更适合作为补充 alpha 或策略组合中的低占比反转腿

## 7. 下一步建议

在这份 shared comparison baseline 之后，最合适的下一步是：

1. 做策略间相关性与互补性分析
2. 做一个两策略组合层
3. 比较：
   - 只做趋势
   - 只做反转
   - 趋势 + 反转组合
