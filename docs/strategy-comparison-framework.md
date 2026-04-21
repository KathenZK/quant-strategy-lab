# 策略对比框架说明

这份文档定义 `Signal Lab` 当前的统一策略对比框架，用于在同一份数据、同一套执行假设下并行比较多条策略。

当前支持的典型对比对象：

- `trend_confirmation`
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

- `src/signal_lab/comparison/config.py`
- `src/signal_lab/comparison/models.py`
- `src/signal_lab/comparison/runner.py`

CLI 入口：

- `signal-lab compare-strategies`

## 3. 对比配置文件

当前推荐使用比较配置文件来驱动统一对比。

示例：

- `configs/strategy_comparison.mvp.baseline.yaml`

结构说明：

```yaml
comparison:
  name: trend_vs_crowding_on_trend_baseline
  description: Compare trend confirmation and crowding reversal on the shared trend MVP baseline dataset.
  workflow_configs:
    - trend_confirmation.mvp.baseline.yaml
    - crowding_reversal.mvp.baseline.yaml
```

说明：

- `workflow_configs` 是策略工作流配置列表
- 路径支持相对路径，默认相对于比较配置文件所在目录解析

## 4. 运行方式

### 先准备共享 baseline 数据

当前更推荐直接使用 shared comparison baseline，而不是单独的 trend-only baseline。

```bash
./.venv/bin/signal-lab seed-shared-comparison-mvp -c configs/app.shared-comparison-baseline.yaml
```

### 再运行统一策略比较

```bash
./.venv/bin/signal-lab compare-strategies --comparison-config configs/strategy_comparison.shared-baseline.yaml -c configs/app.shared-comparison-baseline.yaml
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

## 7. 当前限制

当前框架已经能做“同场对比”，但还没有做：

- 策略间相关性比较
- 月度或区间归因拆分
- regime 分层对比
- 自动最佳策略选择
- 多策略组合层

## 8. 当前推荐用途

这套框架最适合：

- 比较 `trend_confirmation` 与 `crowding_reversal`
- 检查新策略是不是只是在“特殊数据上看起来更好”
- 检查某次参数修改是否改变了策略的结构行为
- 作为回归测试的一部分

## 9. 下一步扩展方向

这套对比框架后续最自然的升级方向是：

1. 加入共同的 shared comparison baseline 场景
2. 增加月度 / regime attribution
3. 计算策略间相关性与互补性
4. 在此基础上进入“多策略组合层”
