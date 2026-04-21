# 拥挤度反转策略 MVP 说明

这份文档定义 `Signal Lab` 当前阶段的第二条正式策略：`crowding_reversal`。

目标：

- 固化拥挤度反转策略的正式 `MVP` 配置
- 提供一份可重复运行的正式工作流配置
- 为后续和 `trend_confirmation` 做并行比较提供统一入口

## 1. 策略定位

`crowding_reversal` 是当前阶段的第二条正式策略。

适用场景：

- 中低频
- 永续合约
- 多空极端拥挤后的反转
- 杠杆资金过热后的均值回归

核心思想：

- 多头过热时：
  - `funding` 偏高
  - `basis` 偏高
  - `OI` 偏高
  - 长周期仍强
  - 但短周期已经出现反转迹象
- 空头过热时逻辑相反
- `liquidations` 继续作为风险层，不单独生成反转方向

## 2. 正式配置文件

### 正式工作流配置

- `configs/crowding_reversal.mvp.yaml`

用途：

- 面向真实数据工作流
- 支持刷新、特征构建、回测、模拟盘

### 基准场景工作流配置

- `configs/crowding_reversal.mvp.baseline.yaml`

用途：

- 面向 deterministic baseline
- 不刷新真实数据
- 当前只输出 backtest 报告

### 基准场景 app 配置

- `configs/app.crowding-baseline.yaml`

用途：

- 把拥挤度反转 baseline 的数据与报告写到独立目录
- 避免污染趋势主线或真实研究环境

## 3. 当前固定的策略参数

信号模式：

- `signal_type: crowding_reversal`

使用的核心因子：

- `ret_24`
- `ret_4`
- `funding_zscore_72`
- `basis_zscore_72`
- `oi_zscore_72`
- `price_oi_regime_4`

当前固定权重：

- `funding_weight = 1.0`
- `basis_weight = 1.0`
- `oi_weight = 0.75`
- `long_term_weight = 0.75`
- `short_term_weight = 1.0`
- `regime_weight = 0.5`

当前固定过滤条件：

- `min_abs_funding_zscore = 1.5`
- `min_abs_basis_zscore = 1.0`
- `min_oi_zscore = 1.0`
- `min_long_term_trend = 0.01`
- `short_term_reversal_floor = 0.0`
- `require_regime_confirmation = true`

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

和趋势主线一样，当前拥挤度反转策略也使用相同的 liquidation 风险 overlay。

固定参数：

- `max_liquidation_spike_zscore = 2.5`
- `max_liquidation_notional_ratio = 0.03`
- `liquidation_weight_scale = 0.25`
- `stop_on_event_cooldown = true`

含义：

- 事件冲击过强时缩小已有目标权重
- cooldown 期间直接暂停该标的开仓

## 5. 推荐运行方式

### 跑正式 `MVP` 工作流

```bash
./.venv/bin/signal-lab run-strategy --workflow-config configs/crowding_reversal.mvp.yaml
```

### 跑基准场景

先写入隔离的基准数据：

```bash
./.venv/bin/signal-lab seed-crowding-mvp -c configs/app.crowding-baseline.yaml
```

再运行基准策略：

```bash
./.venv/bin/signal-lab run-strategy --workflow-config configs/crowding_reversal.mvp.baseline.yaml -c configs/app.crowding-baseline.yaml
```

## 6. 这份 MVP 配置的作用

这份配置不是为了说明“反转策略已经最优”，而是为了提供：

- 一套固定的反转逻辑
- 一套固定的执行假设
- 一条能和趋势主线并行对照的策略线
- 一个后续做参数与组合比较的统一起点
