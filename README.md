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

## 架构约定

- 数据默认共享：相对路径的 app profile 配置会收敛到同一套 `data/`、`reports/` 目录。
- 数据湖只写 canonical 层：`data/raw`、`data/normalized`、`data/features`，不再按策略或时间窗口创建项目专属数据目录。
- active 数据层只保留可追溯的真实交易所来源；synthetic、proxy、test、插值类数据必须隔离到 `data/_quarantine`，不能参与研究回测。
- OHLCV 等周期数据必须显式带 `timeframe`，路径按 `dataset/exchange/market_type/timeframe/date` 分区，`symbol` 保留在文件字段和文件名中。
- 回测结果统一入库：workflow、experiment、comparison 都写入 `reports/_registry/runs.sqlite`。
- 策略自己决定 universe：优先使用 `strategy.symbols` 兼容旧配置；未配置时由策略默认 universe 或 `strategy.strategy_params.symbols` 解析。

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

迁移旧数据湖 profile：

```bash
./.venv/bin/quant-strategy-lab audit-data-lake
./.venv/bin/quant-strategy-lab migrate-data-lake --report-path reports/data_lake_migration.dry-run.json
./.venv/bin/quant-strategy-lab migrate-data-lake --execute --report-path reports/data_lake_migration.json
```

审计并清理非真实数据：

```bash
./.venv/bin/quant-strategy-lab audit-real-data --report-path reports/data_authenticity.audit.json
./.venv/bin/quant-strategy-lab clean-non-real-data --execute --report-path reports/data_authenticity.clean.json
./.venv/bin/quant-strategy-lab audit-real-data --report-path reports/data_authenticity.verify.json
```

运行策略工作流或策略对比：

```bash
./.venv/bin/quant-strategy-lab run-strategy \
  --workflow-config configs/workflows/strategies/spot_cta_trend.binance.spot.1h.local.yaml \
  --use-local-universe \
  --min-avg-dollar-volume 0 \
  --min-history-bars 120 \
  --max-symbols 0 \
  -c configs/environments/binance-spot-1h-local.yaml
```

启动后端 Dashboard API：

```bash
./.venv/bin/quant-strategy-lab dashboard
```

前端位于 `web/`，具体启动命令以 `web/package.json` 为准。

## 保留文档

- `docs/strategy-lab-data-lake-conventions.md`：策略实验室共享数据湖、报告和前端展示约定
- `docs/trend-confirmation-mvp.md`：趋势确认策略说明
- `docs/crowding-reversal-mvp.md`：拥挤度反转策略说明
- `docs/strategy-comparison-framework.md`：策略对比框架说明
- `docs/mvp-implementation-plan.md`：历史实施计划，仅作阶段记录
