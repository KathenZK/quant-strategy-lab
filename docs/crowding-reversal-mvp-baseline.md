# 拥挤度反转策略基准回测报告

这份报告记录 `crowding_reversal` 策略在当前 deterministic baseline 场景上的基准结果。

用途：

- 作为拥挤度反转策略后续迭代的对照基准
- 作为回测链路与配置变更的回归参照
- 用于和 `trend_confirmation` 做并行基准比较

## 1. 基准场景说明

本报告不是基于真实交易所历史数据，而是基于项目内可重复生成的 deterministic crowding 场景。

场景特点：

- `BTC/USDT:USDT`：长周期持续上涨、`funding` 和 `basis` 持续走高、`OI` 堆积，末段出现短期回落
- `ETH/USDT:USDT`：长周期持续下跌、`funding` 和 `basis` 持续走低、`OI` 堆积，末段出现短期反弹
- `SOL/USDT:USDT`：弱信号、作为噪音资产存在
- liquidation 事件按固定时间点写入，用于验证风险 overlay

这样做的目的不是评估真实 alpha，而是：

- 验证反转逻辑能否识别过热/过冷场景
- 验证 `funding / basis / OI` 因子的配合关系
- 验证 liquidation 风险层仍然会生效
- 验证报告链路是否可重复

## 2. 使用的配置

- app 配置：`configs/app/crowding-baseline.yaml`
- workflow 配置：`configs/workflows/strategies/crowding_reversal.mvp.baseline.yaml`
- 数据种子命令：

```bash
./.venv/bin/quant-strategy-lab seed-crowding-mvp -c configs/app/crowding-baseline.yaml
```

- 回测命令：

```bash
./.venv/bin/quant-strategy-lab run-strategy --workflow-config configs/workflows/strategies/crowding_reversal.mvp.baseline.yaml -c configs/app/crowding-baseline.yaml
```

## 3. 本次基准运行

- `run_id`: `20260421T081404Z`
- `signal_name`: `crowding_reversal`
- `strategy_type`: `crowding_reversal`
- `signal_version`: `2c43882b7954f98f`

## 4. 回测指标

- `cumulative_return`: `0.0002`
- `annualized_return`: `0.0003`
- `volatility`: `0.0005`
- `sharpe`: `0.5107`
- `sortino`: `0.0000`
- `max_drawdown`: `-0.0003`
- `calmar`: `0.9240`
- `avg_turnover`: `0.0033`

## 5. 结果解读

这份基准的重点不是收益高，而是验证“反转逻辑有没有按预期触发”。

当前结果说明：

- 反转策略在 deterministic crowding 场景下可以输出稳定的方向信号
- 组合波动和换手依然较低，符合中低频预期
- 在当前这版 synthetic 场景里，反转收益明显弱于 `trend_confirmation`
- 这符合直觉：反转更依赖拐点质量，MVP 阶段不应期望它在所有情景下都强于趋势主线

这份结果最适合做：

- 拥挤度反转参数调优的对照线
- 趋势主线与反转策略的基准比较
- 信号逻辑和风控层变更后的回归检查

不适合做：

- 真实收益预期
- 真实交易部署结论
- 两条策略孰优孰劣的最终判断

## 6. 产物位置

本次运行产物位于：

- 回测报告：`reports/crowding-baseline/runs/crowding_reversal_mvp_baseline/20260421T081404Z/backtest_report.md`
- 运行清单：`reports/crowding-baseline/runs/crowding_reversal_mvp_baseline/20260421T081404Z/run_manifest.json`

## 7. 如何使用这份基准线

后续每次做下面这些改动时，建议都重跑一遍这份 baseline：

- 调整 `funding / basis / OI` 阈值
- 调整反转确认条件
- 修改 `price_oi_regime` 的使用方式
- 修改 liquidation 风险阈值
- 修改组合和权重生成逻辑

如果重跑后这份 baseline 的结果结构发生明显变化，就说明反转策略行为变了，需要进一步解释而不是直接接受。