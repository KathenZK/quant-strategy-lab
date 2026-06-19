# 策略对比框架说明

这份文档定义 `Quant Strategy Lab` 当前的统一策略对比框架，用于在同一份数据、同一套执行假设下并行比较多条策略。

> 状态说明：当前 comparison 已经不再维护独立的 workflow 执行骨架，而是建立在共享的 `batches` / `experiments` 结果收集层之上。文档中的命令与配置格式仍然可用，同时也支持统一的 `run-batch --mode comparison` 入口。

当前支持的典型对比对象：

- `momentum_rotation`
- `crowding_reversal`

## 1. 目标

这套框架解决的是“同场比较”，而不是“多策略组合”。

它的核心目标：

- 在同一份价格与衍生品数据上跑多条策略
- 保证执行假设一致
- 输出一份统一比较报告
- 输出可追溯的比较清单

当前这套框架不做：

- 资金分配优化
- 策略加权组合
- 组合层再平衡

这些属于下一阶段的“多策略组合层”。

## 2. 当前实现位置

代码模块：

- `src/strategy_lab/batches/config.py`
- `src/strategy_lab/batches/runner.py`
- `src/strategy_lab/batches/service.py`
- `src/strategy_lab/experiments/runner.py`
- `src/strategy_lab/comparison/config.py`
- `src/strategy_lab/comparison/models.py`
- `src/strategy_lab/comparison/runner.py`

CLI 入口：

- `quant-strategy-lab compare-strategies`
- `quant-strategy-lab run-batch --mode comparison`

## 3. 对比配置文件

当前推荐使用比较配置文件来驱动统一对比。当前支持两种顶层格式：

示例：

- `configs/comparisons/strategy_comparison.mvp.baseline.yaml`

结构说明：

```yaml
comparison:
  name: momentum_vs_crowding_on_shared_baseline
  description: Compare momentum rotation and crowding reversal on the shared baseline dataset.
  workflow_configs:
    - momentum_rotation.mvp.baseline.yaml
    - crowding_reversal.mvp.baseline.yaml
```

或者：

```yaml
batch:
  name: momentum_vs_crowding_on_shared_baseline
  workflow_configs:
    - momentum_rotation.mvp.baseline.yaml
    - crowding_reversal.mvp.baseline.yaml
```

说明：

- `workflow_configs` 是策略工作流配置列表
- 路径支持相对路径，默认相对于比较配置文件所在目录解析

## 4. 运行方式

### 先准备共享 baseline 数据

共享 baseline 造数命令已经移除。策略比较应直接使用标准 data lake 中可追溯的真实交易所数据。

### 再运行统一策略比较

```bash
./.venv/bin/quant-strategy-lab compare-strategies --comparison-config configs/comparisons/strategy_comparison.shared-baseline.yaml -c configs/environments/shared-comparison-baseline.yaml
```

等价的统一 batch 入口：

```bash
./.venv/bin/quant-strategy-lab run-batch --mode comparison --batch-config configs/comparisons/strategy_comparison.shared-baseline.yaml -c configs/environments/shared-comparison-baseline.yaml
```

## 5. 兼容性要求

为了保证比较公平，当前框架会强制检查：

- `exchange` 必须一致
- `market_type` 必须一致
- `symbols` 必须一致
- `execution assumptions` 必须一致

如果这些条件不满足，比较运行会直接报错。

## 6. 当前输出内容

每次运行会产出：

- 一份比较报告：`comparison_report.md`
- 一份比较清单：`comparison_manifest.json`
- 每条策略单独的回测报告副本
- 一条写入 `reports/_registry/runs.jsonl` 的 comparison 索引记录

当前比较报告会输出：

- 收益对比
- 风险对比
- 换手对比
- 毛收益、交易成本、资金费率成本
- 活跃期比例
- 平均 gross / net exposure
- 最佳贡献标的
- 最差贡献标的
- 最大交易成本来源标的
- 最大资金费率成本来源标的

这些 attribution 字段来自共享的 workflow backtest attribution 结果，而不是 comparison 层单独重复计算。

## 7. 当前限制

当前框架已经能做“同场对比”，但还没有做：

- 策略间相关性比较
- 月度或区间归因拆分
- regime 分层对比
- 自动最佳策略选择
- 多策略组合层

## 8. 当前推荐用途

这套框架最适合：

- 比较 `momentum_rotation` 与 `crowding_reversal`
- 检查新策略是不是只是在“特殊数据上看起来更好”
- 检查某次参数修改是否改变了策略的结构行为
- 作为回归测试的一部分

## 9. 下一步扩展方向

这套对比框架后续最自然的升级方向是：

1. 补充统一 `batch:` 示例与 `run-batch` 使用方式
2. 增加月度 / regime attribution
3. 计算策略间相关性与互补性
4. 在此基础上进入“多策略组合层”

