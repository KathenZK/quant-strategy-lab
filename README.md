# Quant Strategy Lab

本仓库定位为"数据优先"的量化研究档案，而不是通用策略平台。研究对象是**线上可实盘执行的策略**：任何策略在进入 promotion 状态（`live spec`、`dry-run`、`live`）前，都必须先证明它能被真实订单时序复现。本仓库不定义额外的模拟盘阶段；模拟盘/仿真运行统一称为 `dry-run`，真实小额下单归入 `live` 并注明 notional 与风险上限。回测依赖无法真实成交的假设时，它不是"高收益候选"，而是失败诊断——这是本项目从趋势策略和 `HYPE-5M-Pullback-Trail` V2.1A/V3.3/V4 锁仓止损审计中反复付出代价换来的硬门槛（细则见 `.cursor/rules/live-executable-strategy-research.mdc`）。

策略通过研究审计后，在同级仓库 `/Users/ZK/OpenCode/quant-runner` 中实现并进行 dry-run 或小额实盘；交接契约见 `.cursor/rules/lab-runner-handoff.mdc`。

长期维护的核心资产：

- `data/`：本地数据湖。
- `research/`：研究文档、策略家族主账和共享研究内核。
- `src/strategy_lab/`：窄范围、可复用、接口稳定的数据湖/归一化/质量检查/特征/因子工具。

旧策略平台、工作流引擎、Dashboard、泛化回测层和早期规划文档已归档到 `archive/`。

## 先读这些

- `AGENTS.md` 与 `.cursor/rules/`：AI agent 在本仓库工作的约束；细则以 `.cursor/rules/` 为准。
- `research/README.md`：研究档案总入口与家族路由表。
- `research/strategy-status-glossary.md`：策略状态词与状态机的唯一定义。

## 当前结构

```text
data/
 raw/ normalized/ features/ # 本地数据湖核心层
 cache/ external/      # 本地缓存和外部数据

research/
 README.md          # 家族路由表
 strategy-status-glossary.md # 状态机术语表
 _shared-kernels/      # 跨资产共享研究引擎（冻结版本目录）
 hype/ btc/ eth/ sol/ trx/ bnb/  # 单资产策略家族
 asset-portfolios/      # 组合与跨资产研究
 mu/             # MU-HYPE-Transfer（扁平结构，grandfathered）

src/strategy_lab/
 data/    # 最小数据湖内核：layout/schema/normalize/read-write/quality/features/factors

tests/    # active 数据湖内核测试 + 研究文档一致性检查

archive/   # 历史代码、配置、文档、研究和报告快照
```

每个策略家族目录的内部结构（`README.md`、core ledger、`decision-log.md`、`diagnostics/`、`ablations/`、`canonical-specs/`、`live-specs/`、`research-notes/`、`scripts/`、`artifacts/`、`forward-tracking/`）由 `.cursor/rules/research-report-storage.mdc` 与 `.cursor/rules/lab-runner-handoff.mdc` 定义，不在本文件重复。

## 数据湖约定

本仓库只保留一个本地数据湖：`data/raw`、`data/normalized`、`data/features`。不要按策略新建数据根目录；策略研究应显式声明数据来源、交易所、市场类型、周期、symbol 和时间范围。

标准 OHLCV 分区示例：

```text
data/normalized/ohlcv/
 exchange=binance/
  market_type=spot/
   timeframe=1h/
    date=2026-04-30/
     symbol=btc_usdt.parquet
```

查询唯一键是 `exchange + market_type + timeframe + symbol + ts`。`ts` 使用 UTC，`is_closed = true` 的 K 线是研究默认安全口径，`source` 必须标识数据来源。

本仓库不提供通用数据同步 CLI。研究数据维护使用对应 `research/.../scripts/` 下的明确脚本，并在研究文档或 decision log 中记录数据来源、覆盖范围和质量检查结果。

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 运行数据湖内核测试与研究文档一致性检查
pytest tests/
```
