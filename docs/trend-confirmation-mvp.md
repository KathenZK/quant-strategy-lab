# 趋势确认主线 MVP 说明

这份文档定义 `Quant Strategy Lab` 当前阶段的正式 `MVP` 主线策略：`trend_confirmation`。

目标：

- 固化第一条正式主线策略参数
- 提供一份可重复运行的正式工作流配置
- 为后续参数对比和基准回测提供统一参照

## 1. 策略定位

`trend_confirmation` 是当前阶段的第一条正式主线策略。

适用场景：

- 中低频
- 永续合约
- 趋势确认
- 杠杆资金行为确认

核心思想：

- 价格趋势成立
- `OI` 同方向扩张
- `basis` 同方向变化
- `funding` 不能过热
- `liquidations` 作为风险层，不作为主 alpha

## 2. 正式配置文件

### 正式工作流配置

- `configs/workflows/strategies/trend_confirmation.mvp.yaml`

用途：

- 面向真实数据工作流
- 支持刷新、特征构建、回测、模拟盘

### 基准场景工作流配置

- `configs/workflows/strategies/trend_confirmation.mvp.baseline.yaml`

用途：

- 面向 deterministic baseline
- 不刷新真实数据
- 只使用隔离的基准场景数据
- 当前只输出 backtest 报告

### 基准场景环境配置

- `configs/environments/mvp-baseline.yaml`

用途：

- 把基准数据和基准报告写到独立目录
- 避免污染真实研究环境

## 3. 当前固定的策略参数

信号模式：

- `strategy_type: trend_confirmation`

使用的核心因子：

- `ret_24`
- `breakout_20`
- `oi_change_4`
- `basis_change_4`
- `funding_zscore_72`
- `volume_surge_20`

当前固定权重：

- `momentum_weight = 1.0`
- `breakout_weight = 1.0`
- `oi_weight = 1.0`
- `basis_weight = 1.0`
- `volume_weight = 0.5`
- `funding_penalty_weight = 0.5`

当前固定过滤条件：

- `min_momentum = 0.0`
- `min_oi_change = 0.0`
- `min_basis_change = 0.0`
- `breakout_floor = -0.02`
- `min_volume_surge = -0.5`
- `max_abs_funding_zscore = 2.5`

当前固定组合规则：

- `max_long_positions = 2`
- `max_short_positions = 2`
- `long_allocation = 0.5`
- `short_allocation = 0.5`
- `market_neutral = true`

当前固定执行假设：

- `fee_bps = 5.0`
- `slippage_bps = 2.0`
- `starting_cash = 100000`
- `max_abs_weight = 0.2`
- `max_gross_leverage = 1.0`
- `max_net_exposure = 1.0`
- `min_dollar_volume = 1000000`
- `max_funding_rate_abs = 2.5`

## 4. liquidation 风险层参数

当前风险层作为 overlay 使用，不单独生成方向信号。

固定参数：

- `max_liquidation_spike_zscore = 2.5`
- `max_liquidation_notional_ratio = 0.03`
- `liquidation_weight_scale = 0.25`
- `stop_on_event_cooldown = true`

含义：

- 如果 liquidation 风险特征触发阈值，已有方向会降到原权重的 `25%`
- 如果进入 cooldown，直接暂停该标的开仓

## 5. 推荐运行方式

### 跑正式 MVP 工作流

```bash
./.venv/bin/quant-strategy-lab run-strategy --workflow-config configs/workflows/strategies/trend_confirmation.mvp.yaml
```

### 跑基准场景

隔离基准数据写入命令已经移除。后续基准验证必须使用标准 data lake 中可追溯的真实交易所数据。

运行基准策略：

```bash
./.venv/bin/quant-strategy-lab run-strategy --workflow-config configs/workflows/strategies/trend_confirmation.mvp.baseline.yaml -c configs/environments/mvp-baseline.yaml
```

## 6. 这份 MVP 配置的作用

这份配置不是为了说明“这是最优参数”，而是为了提供：

- 一条稳定主线
- 一套固定执行假设
- 一个可复现实验起点
- 一份后续迭代都能对照的基准线

后续如果你继续做参数搜索或第二条策略，建议都以这份配置为默认对照组。