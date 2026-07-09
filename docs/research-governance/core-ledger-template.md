# <Family Full Name> Core Ledger

> 本模板定义主账应写什么。复制到家族目录后，把文件名改为 `<family-id>-core-ledger.md`，并把模板内指向本目录的相对链接改为从家族目录出发的路径（如 `strategy-status-glossary.md` 改为 `../../../docs/research-governance/strategy-status-glossary.md`）。主账是版本身份与状态的事实表，不是实验报告、日志或参数说明书。

## Family Identity

- Full family name：
- Alias：
- Market / exchange / symbol / timeframe：
- Mechanism summary：
- Boundary / collision warnings：

## Current State

- Current version(s)：
- Current status（必须使用 [strategy-status-glossary.md](strategy-status-glossary.md) 中的主状态词）：
- Runner / dry-run / live status：
- Live-readiness blockers：
- Next decision gate：

## Version Rules

- `V1`：
- `Vx.y`：
- Observation / diagnostic rows：
- New version trigger：

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `<Family>-Vx` | `registered / not promoted / not live-ready` | 一句话说明版本身份，不写完整参数表 | 只保留足以识别版本和决策的核心指标；完整切片放报告 | [report.md](relative/path/report.md) | 一句话决策；promotion gate 结果 |

## Shared Assumptions

- Data：
- Cost：
- Execution timing：
- Position sizing：
- Funding / carry：

## Evidence Map

- Specs：
- Diagnostics / ablations：
- Live specs：
- Runner tracking：
- Scripts / artifacts：

## What Not To Put Here

- 不粘贴完整参数表；放到 `specs/`。
- 不粘贴消融网格、逐笔交易、JSON/CSV、图表或命令输出；放到 diagnostics / ablations / artifacts。
- 不把每次研究过程追加成新章节；只更新当前状态、版本表、版本规则和证据链接。
- 不复述 README 的路由信息或 decision-log 的日期流水。
