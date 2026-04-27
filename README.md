# Quant Strategy Lab

`Quant Strategy Lab` 是一个加密量化策略实验平台，当前重点是把数据源、因子、信号、组合回测、实验记录和前端策略实验室串成可重复的研究流程。

## 当前入口

- Python 平台代码：`src/strategy_lab/`
- CLI 入口：`quant-strategy-lab`
- 策略与实验配置：`configs/`
- 前端策略实验室与数据页面：`web/`
- 测试：`tests/`
- 辅助脚本：`scripts/`

## 主要能力

- 数据源接入与本地数据湖
- 因子计算、特征产物与 manifest
- 信号、allocator、策略 facade 与策略注册
- 单策略回测、批量实验、策略对比与运行 registry
- Paper broker、执行会话和风险约束
- 前端页面覆盖策略实验室、回测记录、新闻事件和数据源

## 快速开始

安装 Python 依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

查看 CLI：

```bash
./.venv/bin/quant-strategy-lab --help
./.venv/bin/quant-strategy-lab layout
./.venv/bin/quant-strategy-lab factors
```

运行策略工作流或策略对比：

```bash
./.venv/bin/quant-strategy-lab run-strategy --workflow-config configs/workflows/strategies/trend_confirmation.mvp.yaml
./.venv/bin/quant-strategy-lab compare-strategies --comparison-config configs/comparisons/strategy_comparison.shared-baseline.yaml -c configs/app/shared-comparison-baseline.yaml
```

启动后端 Dashboard API：

```bash
./.venv/bin/quant-strategy-lab dashboard
```

前端位于 `web/`，具体启动命令以 `web/package.json` 为准。

## 保留文档

- `docs/trend-confirmation-mvp.md`：趋势确认策略说明
- `docs/crowding-reversal-mvp.md`：拥挤度反转策略说明
- `docs/strategy-comparison-framework.md`：策略对比框架说明
- `docs/mvp-implementation-plan.md`：历史实施计划，仅作阶段记录
