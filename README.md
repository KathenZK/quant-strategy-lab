# Quant Strategy Lab

本仓库是 data-first 的量化策略研究档案，不是通用策略平台。工作约束、命名口径与硬规则以 [AGENTS.md](AGENTS.md) 和 [`.cursor/rules/`](.cursor/rules/) 为准，本文件不复述细则。

线上执行在同级仓库 `/Users/ZK/OpenCode/quant-runner`；交接与授权边界见 [lab-runner-handoff.mdc](.cursor/rules/lab-runner-handoff.mdc)。

长期维护的核心资产：

- `data/`：本地数据湖。
- `research/`：研究文档、策略家族主账和共享研究内核。
- `src/strategy_lab/`：窄范围、可复用、接口稳定的数据湖/归一化/质量检查/特征/因子工具。

旧策略平台、工作流引擎、Dashboard、泛化回测层和早期规划文档已归档到 `archive/`。

## 先读这些

- [AGENTS.md](AGENTS.md) 与 [`.cursor/rules/`](.cursor/rules/)：AI agent 在本仓库工作的约束；细则以 `.cursor/rules/` 为准。
- [research/README.md](research/README.md)：研究档案总入口与家族路由表。
- [docs/research-governance/strategy-status-glossary.md](docs/research-governance/strategy-status-glossary.md)：策略状态词与状态机的唯一定义。

## 当前结构

```text
data/
  # 本地数据湖，结构见 docs/data-lake-spec.md

research/
  README.md                 # 家族路由表
  _shared-kernels/          # 跨资产共享研究引擎（冻结版本目录）
  hype/ btc/ eth/ sol/ trx/ bnb/ gold/ sox/
                            # 单资产策略家族
  us-indexes/ cn-indexes/   # 指数研究
  asset-portfolios/         # 组合与跨资产研究
  mu/                       # MU-HYPE-Transfer（扁平结构，grandfathered）
  platform/                 # 研究平台（数据湖治理等）

docs/
  data-lake-spec.md         # 数据湖结构与质量规范
  research-governance/      # 清单见 docs/README.md

src/strategy_lab/
  data/    # 最小数据湖内核：layout/schema/normalize/read-write/quality/features/factors

tests/    # active 数据湖内核测试 + 研究文档一致性检查

archive/   # 历史代码、配置、文档、研究和报告快照
```

家族目录内部结构由 [research-report-storage.mdc](.cursor/rules/research-report-storage.mdc) 与 [lab-runner-handoff.mdc](.cursor/rules/lab-runner-handoff.mdc) 定义，本文件不重复。

## 数据湖规范

数据湖的唯一结构与质量规范见 [`docs/data-lake-spec.md`](docs/data-lake-spec.md)；本文件不重复维护具体约定。

## 快速开始

```bash
# 严格按 uv.lock 安装项目和开发依赖
uv sync --locked --extra dev --extra ml

# 与 CI 相同的治理、数据契约和 lint 门禁
uv run --locked --extra dev --extra ml python scripts/governance/preflight.py

# 需要时运行全量测试
uv run --locked --extra dev --extra ml pytest -q
```
