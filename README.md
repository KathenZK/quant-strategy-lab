# Quant Strategy Lab

本仓库现在定位为“数据优先”的量化研究档案，而不是通用策略平台。

长期维护的核心资产是：

- `data/` 下的本地数据湖。
- `docs/research/` 下的研究文档和策略家族台账。
- `docs/research/hype/cursor/` 下的历史 Cursor Canvas 索引。
- `src/strategy_lab/` 下较窄范围的数据、归一化、质量检查、特征和研究导出工具。

旧策略平台、工作流引擎、Dashboard、泛化回测层和早期规划文档已经归档到 `archive/`。

## 先读这些

- `AGENTS.md`：AI agent 在本仓库工作的规则。
- `docs/research/STRATEGY_INDEX.md`：策略家族 id 和版本号防串线规则。
- `docs/research/hype/AI_CONTEXT.md`：阅读 HYPE 研究材料前必须先看的上下文。
- `docs/research/hype/README.md`：HYPE 研究入口。
- `docs/README.md`：文档索引和数据湖约定。

## 当前结构

```text
src/strategy_lab/
  data/       # 数据抓取、归一化、质量检查、因子和特征
  research/   # 可复用的窄口径研究数据集导出工具
  cli.py      # 数据优先的 CLI

docs/research/
  STRATEGY_INDEX.md
  hype/
    AI_CONTEXT.md
    families/
    cursor/

scripts/data/
  fetch_polygon_equity_aggregates.py

archive/
  code/platform/    # 旧策略平台、Dashboard、工作流和测试
  configs/          # 旧顶层环境配置示例
  docs/             # 旧规划和实施文档
  scripts/research/ # 历史一次性研究脚本
  reports/legacy/   # 少量曾经入库的旧报告产物
```

## HYPE 家族规则

不要只引用裸版本号。

请使用明确的家族 id：

- `HYPE-CC-V35`：K 线计数反转家族。
- `HYPE-EMA-X-V14`：EMA 金叉/死叉家族。
- `HYPE-EMA-TB-V35`：EMA 趋势突破家族。
- `MU-HYPE-XFER`：从 HYPE 趋势内核迁移到 MU 的研究方向。

即使版本号相同，它们也是不同策略，不应串联引用。

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

检查数据 CLI：

```bash
./.venv/bin/quant-strategy-lab --help
./.venv/bin/quant-strategy-lab layout
./.venv/bin/quant-strategy-lab factors
```
