# 趋势确认主线基准回测报告

这份报告记录 `trend_confirmation` 主线策略在当前 deterministic baseline 场景上的基准结果。

用途：

- 作为后续策略迭代的对照基准
- 作为回测链路是否退化的回归参照
- 验证 `basis / funding / OI + liquidations` 主链路是否能完整工作

## 1. 基准场景说明

本报告不是基于真实交易所历史数据，而是基于项目内可重复生成的 deterministic 场景。

场景特点：

- `BTC/USDT:USDT`：上涨趋势、`OI` 扩张、`basis` 走强
- `ETH/USDT:USDT`：下跌趋势、`OI` 扩张、`basis` 走弱
- `SOL/USDT:USDT`：弱趋势、噪音更高
- liquidation 事件按固定时间点写入，用于验证风险 overlay

这样做的目的不是评估真实 alpha，而是：

- 验证策略逻辑
- 验证成本建模
- 验证风险层是否会影响权重
- 验证报告链路是否可重复

## 2. 使用的配置

- app 配置：`configs/app/mvp-baseline.yaml`
- workflow 配置：`configs/workflows/strategies/trend_confirmation.mvp.baseline.yaml`
- 数据种子命令：

```bash
./.venv/bin/quant-strategy-lab seed-trend-mvp -c configs/app/mvp-baseline.yaml
```

- 回测命令：

```bash
./.venv/bin/quant-strategy-lab run-strategy --workflow-config configs/workflows/strategies/trend_confirmation.mvp.baseline.yaml -c configs/app/mvp-baseline.yaml
```

## 3. 本次基准运行

- `run_id`: `20260421T075426Z`
- `signal_name`: `trend_confirmation`
- `strategy_type`: `trend_confirmation`
- `signal_version`: `b62ad5a6b3a7c4af`

## 4. 回测指标

- `cumulative_return`: `0.0413`
- `annualized_return`: `0.0434`
- `volatility`: `0.0037`
- `sharpe`: `11.3326`
- `sortino`: `3.9388`
- `max_drawdown`: `-0.0027`
- `calmar`: `16.0863`
- `avg_turnover`: `0.0042`

## 5. 结果解读

这份基准报告要看的是“结构是否合理”，不是“收益是不是高得离谱”。

当前结果说明：

- 主线趋势确认逻辑能在 deterministic 场景中识别强趋势标的
- 组合波动和回撤都较低
- 换手不高，符合中低频预期
- liquidation 风险层已经被纳入主线链路

这份结果最适合做：

- 策略重构前后的回归基准
- 参数微调后的对照线
- 数据层和特征层变更后的健康检查

不适合做：

- 真实收益预期
- 真实交易可行性判断
- 真实资金规模推演

## 6. 产物位置

本次运行产物位于：

- 回测报告：`reports/mvp-baseline/runs/trend_confirmation_mvp_baseline/20260421T075426Z/backtest_report.md`
- 运行清单：`reports/mvp-baseline/runs/trend_confirmation_mvp_baseline/20260421T075426Z/run_manifest.json`

## 7. 后续如何使用这份基准线

后续每次做下面这些改动时，建议都重跑一遍这份 baseline：

- 调整主线因子权重
- 调整 liquidation 风险阈值
- 改数据对齐逻辑
- 改成本模型
- 改组合和权重生成逻辑

如果重跑后这份 baseline 的结构性指标明显变化，就说明主线链路发生了行为变化，需要进一步解释而不是直接接受。
